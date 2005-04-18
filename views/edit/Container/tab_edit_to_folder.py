## Script (Python) "tab_edit_to_folder"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=
##
from Products.Silva.i18n import translate as _

model = context.REQUEST.model
view = context

if model.meta_type != 'Silva Publication':
    return view.tab_edit(message_tye="error",
                         message=_("Can only change Publications into Folders"))

id = model.id
parent = model.aq_parent
model.to_folder()
model = getattr(parent, id)
context.REQUEST.set('model', model)
message = _("Changed into folder")
return model.edit['tab_settings'](message_type="feedback", message=message)
