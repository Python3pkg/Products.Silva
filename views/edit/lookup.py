request = context.REQUEST
session = request.SESSION
model = request.model

key = ('silva_lookup_referer', model.get_root_url())
default_referer = '%s/edit/tab_access' % model.absolute_url()
referer = request.get('HTTP_REFERER', default_referer)

# XXX Quick hack to fix issue791
if referer.endswith('/edit/'):
    referer = default_referer

session[key] = referer

request.RESPONSE.redirect('%s/edit/lookup_ui' % model.absolute_url())