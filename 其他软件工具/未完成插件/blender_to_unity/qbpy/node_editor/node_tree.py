import bpy
from bpy.types import NodeTree


class Tree(NodeTree):
    """Base Node Tree Class"""

    def execute(self, context):
        """Execute the node tree"""

        for node in self.nodes:
            node.execute(context)
