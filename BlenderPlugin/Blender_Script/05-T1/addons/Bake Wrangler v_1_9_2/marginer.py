import numpy as np

# Main loop over image broken into segments. Will try to calculate pixel values outside of
# the masked area using the preconfigured weighting system.
def worker(hunk, shm_pixels, shm_mask, shm_bools, shm_margin, margin, limit, hit_target):
    np_pixels = np.ndarray(shm_pixels[1], dtype=shm_pixels[2], buffer=shm_pixels[0].buf)
    np_mask = np.ndarray(shm_mask[1], dtype=shm_mask[2], buffer=shm_mask[0].buf)
    np_bools = np.ndarray(shm_bools[1], dtype=shm_bools[2], buffer=shm_bools[0].buf)
    margins_bool = np.ndarray(shm_margin[1], dtype=shm_margin[2], buffer=shm_margin[0].buf)
    hit_stub = np.zeros((0,3))
    lim = len(margins_bool) if not limit else limit
    for multi_index in hunk:
        # Index ranges to create local view of arrays centred on pixel
        view_idx = [multi_index[0],
                    multi_index[0]+(margin*2)+1,
                    multi_index[1],
                    multi_index[1]+(margin*2)+1]
        bool_view = np_bools[view_idx[0]:view_idx[1],view_idx[2]:view_idx[3]]
        hit_max = np.count_nonzero(bool_view) # Count number of non alpha pixels in view
        if hit_max:
            pixel_view = np_pixels[view_idx[0]:view_idx[1],view_idx[2]:view_idx[3]] # Get view of pixel data
            hit_targ = hit_max if hit_max < hit_target else hit_target
            hits = hit_stub
            iteration = 0
            # Majority of time cost is here due to arrays being copied in every case
            while hits.shape[0] < hit_targ and iteration < lim:
                sub_bool = bool_view[margins_bool[iteration]]
                if np.count_nonzero(sub_bool):
                    sub_pixel = pixel_view[margins_bool[iteration]]
                    hits = np.append(hits, sub_pixel[sub_bool,:3], axis=0) if hits.shape[0] else sub_pixel[sub_bool,:3]
                iteration += 1
            # Get average of selected pixels colour and write value
            if hits.shape[0] >= hit_target:
                np_pixels[multi_index[0]+margin, multi_index[1]+margin,:3] = hits.sum(0) / hits.shape[0]
                np_mask[multi_index[0]+margin, multi_index[1]+margin] = 1.0


# Simply writes pixels to a bpy.image. This is to keep bpy outside of the main working loop
def write_back(image, pixels):
    import bpy
    image.pixels.foreach_set(pixels.ravel())
    image.update()


# Create numpy arrays of the image and mask as well as set up a weighting system for sampling
# pixels within the margin step area
def set_up(image, mask, margin):
    import bpy
    # Load numpy array from input image and mask
    w, h = image.size
    np_pixels = np.zeros((w, h, 4), 'f')
    np_mask = np.zeros((w, h, 4), 'f')
    image.pixels.foreach_get(np_pixels.ravel())
    mask.pixels.foreach_get(np_mask.ravel())
        
    # Create a weighting system for pixel samples within the margin area
    px_offsets = np.array(np.meshgrid(np.arange(0,margin*2+1), np.arange(0,margin*2+1)))
    px_offsets = np.moveaxis(px_offsets, 0, -1) # Change to X by Y by 2
    px_offsets = np.absolute(px_offsets - [margin,margin])
    # Manhattan distance array
    #px_manhat = px_offsets.sum(2)
    # Euclid distances
    px_euclid = np.sqrt(np.power(px_offsets[:,:,0],2) + np.power(px_offsets[:,:,1],2))
    px_euclid_c = np.int_(np.ceil(px_euclid))
    px_euclid_r = np.int_(np.round(px_euclid))
    # Bool arrays for each weight level starting at 1
    margins_bool = []
    for i in range(1,margin+1):
        margins_bool.append(px_euclid_r == i)
    
    # Expand pixel data by margin size by copying the start onto the end to hopefully make iteration faster
    # (negative array indexes work, but you can't exceed array bounds)
    np_pixels = np.vstack((np_pixels, np_pixels[0:margin,:,:]))         # Add <margin> rows from the bottom to the top
    np_pixels = np.vstack((np_pixels[h-margin:h,:,:], np_pixels))       # Add <margin> rows from old top to the new top
    np_pixels = np.hstack((np_pixels, np_pixels[:,0:margin,:]))         # Add <margin> cols from left to right
    np_pixels = np.hstack((np_pixels[:,w-margin:w,:], np_pixels))       # Add <margin> cols from old right to new right
    # Do same for mask
    np_mask = np.vstack((np_mask, np_mask[0:margin,:,:]))         # Add <margin> rows from the bottom to the top
    np_mask = np.vstack((np_mask[h-margin:h,:,:], np_mask))       # Add <margin> rows from old top to the new top
    np_mask = np.hstack((np_mask, np_mask[:,0:margin,:]))         # Add <margin> cols from left to right
    np_mask = np.hstack((np_mask[:,w-margin:w,:], np_mask))       # Add <margin> cols from old right to new right
    # Reduce mask values to just reds to save space
    np_mask = np_mask[...,0].copy()
    np_bool = np_mask > 0.9
    
    return np_pixels, np_mask, np_bool, np.asarray(margins_bool), w, h, margin
                    

# Takes all the outputs from the setup routine (not called from within to avoid interacting with
# bpy in the subprocesses). Creates shared memory versions of the data and spawns a bunch of
# processes to work on smaller hunks of pixels in parallel.
def add_margin(pixels, mask, bools, margins, w, h, margin_step, margin, hit_target):
    import concurrent.futures
    from multiprocessing.managers import SharedMemoryManager
    m_step = margin_step if margin >= margin_step or margin == -1 else margin
    with SharedMemoryManager() as smm:
        # Create shared memory versions of these arrays for the processes to share
        shm_pixels = smm.SharedMemory(size=pixels.nbytes)
        shm_mask = smm.SharedMemory(size=mask.nbytes)
        shm_bools = smm.SharedMemory(size=bools.nbytes)
        shm_margin = smm.SharedMemory(size=margins.nbytes)
        np_pixels = np.ndarray(pixels.shape, dtype=pixels.dtype, buffer=shm_pixels.buf)
        np_pixels[:] = pixels[:]
        del pixels
        np_mask = np.ndarray(mask.shape, dtype=mask.dtype, buffer=shm_mask.buf)
        np_mask[:] = mask[:]
        del mask
        np_bools = np.ndarray(bools.shape, dtype=bools.dtype, buffer=shm_bools.buf)
        np_bools[:] = bools[:]
        del bools
        margins_bool = np.ndarray(margins.shape, dtype=margins.dtype, buffer=shm_margin.buf)
        margins_bool[:] = margins
        del margins
        
        # Split work into smaller hunks to split between cpu cores
        import os
        cpus = os.cpu_count() * 2
        mask_where = np.argwhere(np_bools[margin_step:w+margin_step,margin_step:h+margin_step] == False)
        hunks = np.array_split(mask_where, cpus)
        
        # Do the processing in parallel
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = []
            limit = 0
            # Negative margin indicates complete fill is wanted
            if margin == -1:
                # Simply keep processing hunks until they come back empty
                while len(hunks[0]) > 0:
                    for i in hunks:
                        futures.append(executor.submit(worker, i, [shm_pixels, np_pixels.shape, np_pixels.dtype], [shm_mask, np_mask.shape, np_mask.dtype], [shm_bools, np_bools.shape, np_bools.dtype], [shm_margin, margins_bool.shape, margins_bool.dtype], m_step, limit, hit_target))
                    # Wait for this steps hunks to finish, then calculate the next set
                    concurrent.futures.wait(futures)
                    np_bools[:] = np_mask > 0.9
                    mask_where = np.argwhere(np_bools[margin_step:w+margin_step,margin_step:h+margin_step] == False)
                    hunks = np.array_split(mask_where, cpus)
            # Check the margin actually has a size before doing anything
            elif margin > 0:
                # Work out how many steps are needed and if a last sub step size pass will be needed at the end
                steps = int(margin / m_step)
                lasts = margin % m_step
                if lasts: steps += 1
                # Process all hunks for each step in parallel
                for step in range(steps):
                    # If the margin step didn't fit evenly a last sub sized step will be done to fill it
                    if lasts and step == steps-1:
                        limit = lasts
                    for i in hunks:
                        futures.append(executor.submit(worker, i, [shm_pixels, np_pixels.shape, np_pixels.dtype], [shm_mask, np_mask.shape, np_mask.dtype], [shm_bools, np_bools.shape, np_bools.dtype], [shm_margin, margins_bool.shape, margins_bool.dtype], m_step, limit, hit_target))
                    # Wait for this steps hunks to finish, then calculate the next set if there are more steps
                    concurrent.futures.wait(futures)
                    if step < steps-1:
                        np_bools[:] = np_mask > 0.9
                        mask_where = np.argwhere(np_bools[margin_step:w+margin_step,margin_step:h+margin_step] == False)
                        hunks = np.array_split(mask_where, cpus)
        
        # Copy pixels from shared memory before the smm exits
        output_px = np_pixels[margin_step:w+margin_step,margin_step:h+margin_step].copy()
    return output_px


if __name__ == '__main__':
    pass