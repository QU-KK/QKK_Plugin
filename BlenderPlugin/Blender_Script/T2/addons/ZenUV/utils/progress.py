# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

""" Attempts to make something with Blender WindowManager progress """
from __future__ import annotations

import bpy

from timeit import default_timer as timer
from ZenUV.utils.clib.lib_init import init_progress, finish_progress
from ZenUV.prop.zuv_preferences import get_prefs

_ATTR_PROGRESS_LOCK = 'zen_sets_progress_lock'


class ProgressCancelException(Exception):
    pass


class ProgressText:

    def __init__(self):
        self.prefix = ""
        self.preposition = ""


class ProgressBar:

    def __init__(self, context, iterations, text_only=True) -> None:

        addon_prefs = get_prefs()
        if addon_prefs.use_progress_bar:
            self.pb = init_progress(context, message="", text_only=text_only)
        else:
            self.pb = None
        self.current_step = 0
        self.force = False
        self.iterations = iterations
        self.text_processor = ProgressText()
        self.obj_name_len = 20
        self.last_update_time = 0
        self.init_time = timer()
        self.fps = 15

    def __del__(self):
        if self.pb is not None:
            finish_progress(self.pb)

    def set_text(self, prefix="", preposition=""):
        self.text_processor.prefix = prefix
        self.text_processor.preposition = preposition

    def set_text_relax(self, obj_name="", cluster_name="", preposition=""):
        name_len = len(obj_name)
        if name_len > self.obj_name_len:
            stripped_part = self.obj_name_len // 2
            obj_name = obj_name[0:stripped_part] + ".." + obj_name[name_len - stripped_part:name_len]
        if name_len == 0:
            self.text_processor.prefix = f"{cluster_name}: "
        else:
            self.text_processor.prefix = f"{obj_name} -> {cluster_name}: "
        self.text_processor.preposition = preposition

    def update(self):
        return self._setTaskbarProgress()

    def updateSpinner(self):
        return self._setTaskbarSpinnerProgress()

    def update_by_timer(self):
        """
        'current_step' should be set manually before
        """
        if self.pb:
            delta = timer() - self.last_update_time

            if delta > 1.0 / self.fps:  # NOTE: 15 FPS by default
                self.last_update_time = timer()
                return self._setTaskbarProgressManual()

        return True

    def finish(self):
        if self.pb is not None:
            finish_progress(self.pb)

    def _getPercent(self):
        percent = 0
        if self.iterations != 0:
            if not percent > 100:
                percent = int(round(self.current_step / self.iterations * 100, 0))
            else:
                percent = 100
        return percent

    def _getText(self):
        return f"{self.text_processor.prefix} {self._getPercent()} {self.text_processor.preposition} 100%"

    def _getSpinnerText(self):
        delta = timer() - self.init_time
        return f"{self.text_processor.prefix} {delta:.3f} sec"

    def _setTaskbarProgress(self):
        self.current_step += 1
        if self.pb:
            return self.pb.setTaskbarProgress(self.current_step, self.iterations, self.force, text=self._getText())
        return True

    def _setTaskbarProgressManual(self):
        if self.pb:
            return self.pb.setTaskbarProgress(self.current_step, self.iterations, self.force, text=self._getText())
        return True

    def _setTaskbarSpinnerProgress(self):
        if self.pb:
            return self.pb.setTaskbarProgress(
                self.current_step, self.iterations, self.force, text=self._getSpinnerText())
        return True

    @classmethod
    def check_update_spinner_progress(cls, progress: ProgressBar):
        if progress and progress.pb:
            delta = timer() - progress.last_update_time

            if delta > 1.0 / progress.fps:  # NOTE: 15 FPS by default
                progress.last_update_time = timer()
                if not progress.updateSpinner():
                    raise ProgressCancelException()

        return True


def _is_progress_locked():
    return (
        _ATTR_PROGRESS_LOCK in bpy.app.driver_namespace.keys()) \
        and bpy.app.driver_namespace[_ATTR_PROGRESS_LOCK]


def start_progress(context, min=0, max=100, high_priority=False):
    if high_priority:
        bpy.app.driver_namespace[_ATTR_PROGRESS_LOCK] = True
    else:
        if _is_progress_locked():
            return

    context.window_manager.progress_begin(min, max)


def update_progress(context, val, high_priority=False):
    if high_priority is False and _is_progress_locked():
        return
    else:
        context.window_manager.progress_update(val)


def end_progress(context, high_priority=False):
    if high_priority:
        bpy.app.driver_namespace[_ATTR_PROGRESS_LOCK] = False
    else:
        if _is_progress_locked():
            return

    context.window_manager.progress_end()
