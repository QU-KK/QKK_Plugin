from typing import List

class CommonList():

    """ Common methods for all lists """


    @property
    def active(self):
        
        # me aseguro de que el indice esta dentro del rango:
        if not (0 <= self.list_index < self.length):
            return            
            
        return self.list[self.list_index]


    @property
    def is_void(self) -> bool:
        return False if len(self.list) > 0 else True


    @property
    def length(self) -> int:
        return len(self.list)
    

    @property
    def get_active_id(self) -> str:

        active = self.active
        if not active:
            return
        
        return active.id_name
    

    @property
    def get_all_items(self) -> List:
        return [item for item in self.list]
    

    @property
    def get_all_items_names(self) -> List:
        return [item.label_txt for item in self.list]


    @property
    def get_all_items_ids(self) -> List:
        return [item.id_name for item in self.list]


    def get_item_from_id(self, id_name:str):
        for list_item in self.list:
            if list_item.id_name == id_name:
                return list_item


    def remove_item(self, id_to_rm:str) -> None:
        idx = next((idx for idx, item in enumerate(self.list) if item.id_name == id_to_rm), None)
        self.list.remove(idx)
        self.list_index = self.length-1
