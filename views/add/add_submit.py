## Script (Python) "add_submit"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=
##
from Products.Silva.helpers import check_valid_id, IdCheckValues

model = context.REQUEST.model
view = context
REQUEST = context.REQUEST

# if we cancelled, then go back to edit tab
if REQUEST.has_key('add_cancel'):
    return model.edit['tab_edit']()

# validate form
from Products.Formulator.Errors import ValidationError, FormValidationError
try:
    result = view.form.validate_all(REQUEST)
except FormValidationError, e:
    # in case of errors go back to add page and re-render form
    return view.add_form(message_type="error", message=view.render_form_errors(e))

# get id and title from form, convert title to unicode
id = result['object_id']
# remove them from result dictionary
del result['object_id']

# try to cope with absence of title in form (happens for ghost)
if result.has_key('object_title'):
    title = model.input_convert(result['object_title'])
    del result['object_title']
else:
    title = ""

# if we don't have the right id, reject adding
id_check = check_valid_id(model, id)
if not id_check == IdCheckValues.ID_OK:
    return view.add_form(message_type="error", message=view.get_id_status_text(id, id_check))

# process data in result and add using validation result
object = context.add_submit_helper(model, id, title, result)

# update last author info in new object
object.sec_update_last_author_info()

# now go to tab_edit in case of add and edit, back to container if not.
if REQUEST.has_key('add_edit_submit'):
    REQUEST.RESPONSE.redirect(object.absolute_url() + '/edit/tab_edit')
else:
    return model.edit['tab_edit'](message_type="feedback", 
                         message="Added %s %s." % (object.meta_type, view.quotify(id)))
