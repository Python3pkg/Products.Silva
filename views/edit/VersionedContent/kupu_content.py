## Script (Python) "get_edit_mode"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=
##
view = context
request = view.REQUEST
model = request.model

context.set_cache_headers()
context.set_content_type()
xhtml = model.editor_storage(editor='kupu')

return ('<html>\n'
        '<head>\n'
        '<title>%s</title>\n'
        '<link type="text/css" rel="stylesheet" href="%s" />\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />\n'
        '</head>\n'
        '%s\n'
        '</html>' % (model.get_title_editable(), 
                        getattr(context.globals, 'kupu.css').absolute_url(),
                        xhtml))
