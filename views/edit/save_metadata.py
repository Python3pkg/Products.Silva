from Products.Silva.i18n import translate as _

request = context.REQUEST
model = request.model
view = context
ms = context.service_metadata

editable = model.get_editable()
binding = ms.getMetadata(editable)
all_errors = binding.setValuesFromRequest(request)

if all_errors:
    # There were errors...
    type = 'error'
    msg = _(
        'The data that was submitted did not validate properly '
        '(you might want to use the browser back button to adjust '
        'the form values).')
else:
    type = 'feedback'
    msg = _('Metadata saved.')
    model.sec_update_last_author_info()

templateid = request.form.get('returntotab', 'tab_metadata')
method = getattr(view, templateid)
return method(
    form_errors=all_errors, message_type=type, message=msg)
