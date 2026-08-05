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

from .utils import print_backtrace, print_backtrace_if_debug, get_prefs, get_main_props
from .app_iface import Operator


class UVPM4_OT_Generic(Operator):
    
    UNEXPECTED_ERROR_MSG = 'Unexpected error - contact support@uvpackmaster.com for assistance'

    def handle_unexpected_error(self, ex):
        print_backtrace(ex)
        self.report({'ERROR'}, self.UNEXPECTED_ERROR_MSG)

    def redraw_context_area(self):
        self.context.area.tag_redraw()


class UVPM4_OT_GenericHandler(UVPM4_OT_Generic):

    ACTIVE_META_VALUE = '__active__'
    mode = None

    def mode_kwargs(self):
        return {}
    
    def get_active_mode_id(self):
        return None

    def get_mode(self):
        if self.mode is not None:
            return self.mode

        mode_id = None

        if hasattr(self, 'mode_id') and self.mode_id != '':
            mode_id = self.mode_id

        elif hasattr(self, 'MODE_ID'):
            mode_id = self.MODE_ID

        if mode_id is not None:
            if mode_id == self.ACTIVE_META_VALUE:
                mode_id = self.get_active_mode_id()

                if mode_id is None:
                    return None

            self.mode = get_prefs().get_mode(mode_id, self.context, **self.mode_kwargs())
            return self.mode
        
        return None

    def execute(self, context):
        try:
            self.context = context
            self.prefs = get_prefs()

            from .spipeline.engine.props import MainProps
            self.main_props : MainProps = get_main_props(context)

            return self.execute_impl(context)

        except RuntimeError as ex:
            print_backtrace_if_debug(ex)
            self.report({'ERROR'}, str(ex))

        except Exception as ex:
            self.handle_unexpected_error(ex)

        return {'FINISHED'}
