##parameters=name=None
from Products.Silva.i18n import translate as _

request = context.REQUEST
session = request.SESSION
model = request.model

if not name:
    name = request.form.get('name', ' ')
name = name.strip()

if name == '':
    return context.lookup_ui_direct(
        message_type="error",
        message=_("No username supplied."))

selection = context.lookup_get_selection()
selection[name] = 1

msg = _("Added username to clipboard: ${string}", mapping={'string': name})
return context.lookup_ui_direct(
    message_type="feedback",
    message=msg)