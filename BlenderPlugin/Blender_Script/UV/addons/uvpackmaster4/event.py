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


def key_release_event(event):
    return (event.type not in {'MIDDLEMOUSE', 'INBETWEEN_MOUSEMOVE', 'MOUSEMOVE', 'TIMER', 'TIMER_REPORT', 'WHEELDOWNMOUSE', 'WHEELUPMOUSE'} and event.value == 'PRESS')

def mouse_move_or_wheel_event(event):
    return event.type in {'MIDDLEMOUSE', 'INBETWEEN_MOUSEMOVE', 'MOUSEMOVE', 'TIMER', 'TIMER_REPORT', 'WHEELDOWNMOUSE', 'WHEELUPMOUSE'}

def esc_press_event(event):
    return (event.type in {'ESC'} and event.value == 'PRESS')

def space_press_event(event):
    return (event.type in {'SPACE'} and event.value == 'PRESS')


class EscPressFinishConditionMixin:

    def operation_done_finish_condition(self, event):
        return esc_press_event(event)

    def operation_done_hint(self):
        return 'press ESC to close the summary'


class DefaultFinishConditionMixin:

    def operation_done_finish_condition(self, event):
        return key_release_event(event)

    def operation_done_hint(self):
        return 'press any key to close the summary'
