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

# Copyright 2023, Alex Zhornyak

import bpy


class ZuvReporter:

    LITERAL_REPORT = 'zenuv_op_reports'

    def report_ex(self: bpy.types.Operator, cat: set, message: str):
        p_reports = bpy.app.driver_namespace.get(ZuvReporter.LITERAL_REPORT, {})
        p_reports[self.bl_idname] = (cat, message)
        bpy.app.driver_namespace[ZuvReporter.LITERAL_REPORT] = p_reports
        self.report(cat, message)

    def report_clear(self: bpy.types.Operator):
        p_reports = bpy.app.driver_namespace.get(ZuvReporter.LITERAL_REPORT, {})
        p_reports[self.bl_idname] = None
        bpy.app.driver_namespace[ZuvReporter.LITERAL_REPORT] = p_reports

    @classmethod
    def get_last_report(cls, idname: str):
        p_reports = bpy.app.driver_namespace.get(ZuvReporter.LITERAL_REPORT, {})
        if p_reports:
            return p_reports.get(idname, None)
        return None
