import Globals
from Products.Silva.adapters import adapter
from Products.Silva.transform.interfaces import IRenderable

class RenderableAdapter(adapter.Adapter):

    __implements__ = IRenderable

    def view(self):
        """Display the view of this version using the selected renderer.
        
        Returns the rendered content or None if no renderer can be
        found.
        """
        renderer_name = self.context.get_renderer_name()
        renderer = self.context.service_renderer_registry.getRenderer(
            self.context.get_silva_object().meta_type, renderer_name)
        if renderer is None:
            return None
        return unicode(renderer.render(self.context), 'UTF-8')
            
Globals.InitializeClass(RenderableAdapter)

def getRenderableAdapter(context):
    return RenderableAdapter(context).__of__(context)
    