import bpy
from bpy.types import Node
from bpy.props import *


class Node(Node):
    def input(self, type, name, default=None):
        """
        Create a new input socket and return it

        type (NodeSocketType) - The type of the socket
        name (str) - The name of the socket
        default (any) - The default value of the socket
        return (NodeSocket) - The newly created socket
        """
        input = self.inputs.new(type, name)
        if default:
            input.default_value = default
        return input

    def output(self, type, name, default=None):
        """
        Create a new output socket and return it

        type (NodeSocketType) - The type of the socket
        name (str) - The name of the socket
        default (any) - The default value of the socket
        return (NodeSocket) - The newly created socket
        """
        output = self.outputs.new(type, name)
        if default:
            output.default_value = default
        return output

    def execute(self, context):
        """Execute the node"""

        pass
