"""
module for conversion from current 

   RealObjects' 3.0 XHTML 
   
       to

   silva (0.9.2/cvs) 

This transformation tries to stay close to
how silva maps its xml to html. I am not sure, though,
whether this is a good idea because RealObjects 2.11 
currently let's the user select 'h1' and 'h2' as styles
and we don't want that.

the notation used for the transformation roughly
follows the ideas used with XIST (but is simpler).
Note that we can't use XIST itself as long as 
silva is running on a Zope version that 
doesn't allow python2.2

"""

__author__='holger krekel <hpk@trillke.net>'
__version__='$Revision: 1.3 $'

try:
    from transform.base import Element, Text, Frag
except ImportError:
    from Products.Silva.transform.base import Element, Text, Frag

import silva

DEBUG=0

class html(Element):
    def convert(self, context):
        """ forward to the body element ... """
        headtag = self.find_one('head')
        bodytag = self.find_one('body')
        headtag.convert(context)
        doc = bodytag.convert(context)

        return silva.silva_document(
                silva.title(context.title),
                doc,
                id = context.id)

class head(Element):
    def convert(self, context):
        """ ignore """
        self.content.convert(context)

class meta(Element):
    def convert(self, context):
        """ ignore """
        name = self.attrs.get('name')
        if name:
            setattr(context, name, self.attrs['content'])
        return None

class title(Element):
    def convert(self, context):
        """ ignore """
        return u''

class body(Element):
    "html-body element"
    def convert(self, context):
        return silva.doc(
            self.content.convert(context)
        )

class doctitle(Element):
    def convert(self, context):
        context.title = self.extract_text()

class term(Element):
    def convert(self, context):
        return silva.dt(self.content.convert(context))

class desc(Element):
    def convert(self, context):
        return silva.dd(self.content.convert(context))

class h1(Element):
    def convert(self, context):
        return u''

class h2(Element):
    ""
    def convert(self, context):
        return u''

class h3(Element):
    ""
    def convert(self, context):
        result = silva.heading(
            self.content.convert(context),
            type="normal"
            )
        return self.process_result(result, context)

    def process_result(self, result, context):
        if hasattr(context, 'toplist_result'):
            context.toplist_result.append(result)
        else:
            return result

class h4(h3):
    ""
    def convert(self, context):
        result = silva.heading(
            self.content.convert(context),
            type="sub"
            )
        return self.process_result(result, context)

class h5(h3):
    """ List heading """
    def convert(self, context):
        """ return a normal heading. note that the h5-to-title
            conversion is done by the html list-tags themselves. 
            Thus h5.convert is only called if there is no
            list context and therefore converted to a subheading.
        """
        result = silva.heading(
            self.content.convert(context),
            type="subsub",
            )
        return self.process_result(result, context)

class h6(h3):
    def convert(self, context):
        """ this only gets called if the user erroronaously
            used h6 somewhere 
        """
        result = silva.heading(
            self.content.convert(context),
            type="paragraph",
            )
        return self.process_result(result, context)
    
class h7(h3):
    def convert(self, context):
        """ this only gets called if the user erroronaously
            used h6 somewhere 
        """
        result = silva.p(
            self.content.convert(context),
            type="normal",
            )
        return self.process_result(result, context)

class p(Element):
    """ the html p element can contain nodes which are "standalone"
        in silva-xml. 
    """
    def convert(self, context):
        pre,img,post = self.find_and_partition('img')
        type = self.attrs.get('silva_type', None)
        if pre:
            pre = silva.p(pre.convert(context), type=type)
        if img:
            img = img.convert(context)
        if post:
            post = silva.p(post.convert(context), type=type)

        if not (pre or img or post):
            pre = silva.p(type=type)

        return Frag(
            pre, 
            img,
            post,
        )

class ul(Element):
    """ difficult list conversions.

        note that the html list constructs are heavily
        overloaded with respect to their silva source nodes.
        they may come from nlist,dlist,list, 
        there are lots of different types and the silva and 
        html type names are different. 

        ol shares the same implementation except it has
        different "default_types"

    """
    default_types = ('disc','circle','square','none')

    def convert(self, context):
        hadctx = hasattr(context, 'toplist_result')
        if not hadctx:
            context.toplist_result = context.resultstack[-1]

        if self.is_dlist(context):
            result = self.convert_dlist(context)
        elif self.is_nlist(context):
            result = self.convert_nlist(context)
        else:
            result = self.convert_list(context)

        if not hadctx:
            del context.toplist_result 
        return result

    def is_nlist(self, context):

        for i in self.compact().find():
            if i.name() != 'li':
                return 1

        for i in self.content.flatten():
            if i.name() in ('ul', 'ol'):
                return 1

    def convert_list(self, context):
        type = self.get_type()

        return silva.list(
            self.content.convert(context),
            type=type
        )


    def convert_nlist(self, context):

        type = self.get_type()

        lastli = None
        content = Frag()
        for tag in self.content.convert(context):
            name = tag.name()
            if name == 'li':
                lastli = tag
                tag.content = silva.mixin_paragraphs(tag.content)
            elif tag.compact():
                #if not lastli:
                tag = silva.li(tag)
                #else:
                #    lastli.content.append(tag)
                #    lastli = None
                #    continue
            content.append(tag)

        res = silva.nlist(
            content,
            type=type)
        return res
                    

        # corrections to the resulting xml 
        lastli = None
        for count in xrange(len(res.content)):
            tag = res.content[count]
            if tag.name()=='li':
                lastli=tag
                tag.content = silva.mixin_paragraphs(tag.content)
            elif tag.compact():
                if not lastli:
                    #print "replacing",count,"in",res.asBytes()
                    res.content[count]= silva.li(tag)
                else:
                    lastli.content.append(tag)

        return res

    def get_type(self):
        type = self.attrs.get('type', None)
        if type is not None:
            type = type.lower()

        if type not in self.default_types:
            type = self.default_types[0]
        return type

    def is_dlist(self, context):
        for item in self.find('li'):
            if item.find('term'):
                return 1
        
    def convert_dlist(self, context):
        tags = []
        for item in self.find('li'):
            term = item.find('term')
            if term:
                desc = item.find('desc') 
                tags.append(term[0].convert(context))
                tags.append(desc and desc.convert(context) or 
                            silva.dd(''))
        return silva.dlist(
            type='normal',
            *tags
            )



class ol(ul):
    default_types = ('1','a','i')

class li(Element):
    def convert(self, context):

        return silva.li(
            self.content.convert(context),
            )

class strong(Element):
    def convert(self, context):
        return silva.strong(
            self.content.convert(context),
            )

class b(strong):
    pass

class em(Element):
    def convert(self, context):
        return silva.em(
            self.content.convert(context),
            )

class i(em): 
    pass

class u(Element):
    def convert(self, context):
        return silva.underline(
            self.content.convert(context),
            )

class sub(Element):
    def convert(self, context):
        return silva.sub(
            self.content.convert(context),
            )

class sup(Element):
    def convert(self, context):
        return silva.super(
            self.content.convert(context),
            )


class font(Element):
    def convert(self, context):
        color = self.attrs.get('color')
        tag = {'aqua': silva.super, 
               'green': silva.dt,
               'blue': silva.sub,
               }.get(color)
        if tag:
            return tag(
                self.content.convert(context)
            )
        else:
            return self.content.convert(context)

class a(Element):
    def convert(self, context):
        return silva.link(
            self.content.convert(context),
            url=self.attrs['href']
            )

class img(Element):
    def convert(self, context):
        from urlparse import urlparse
        src = self.attrs['src'].content
        src = urlparse(src)[2]
        link = self.attrs.get('link')
        if src.endswith('/image'):
            src = src[:-len('/image')]
        alignment=self.attrs.get('align')
        return silva.image(
            self.content.convert(context),
            path=src,
            link=link,
            alignment=alignment,
            )

class br(Element):
    def convert(self, context):
        return silva.br()

class pre(Element):
    def compact(self):
        return self

    def convert(self, context):
        return silva.pre(
            self.content.convert(context)
        )

class table(Element):
    def convert(self, context):
        rows = self.content.find('tr')
        if len(rows)>0:
            cols = len(rows[0].find('td'))
        return silva.table(
                self.content.convert(context),
                columns=self.attrs.get('cols', cols),
                column_info = self.attrs.get('silva_column_info'),
                type=self.attrs.get('silva_type')
            )

class tr(Element):
    def convert(self, context):
        return silva.row(
            self.content.convert(context)
        )

class td(Element):
    def convert(self, context):
        return silva.field(
            self.content.convert(context)
        )

"""
current mapping of tags with silva
h1  :  not in use, reserved for (future) Silva publication
       sections and custom templates
h2  :  title
h3  :  heading
h4  :  subhead
h5  :  list title
"""
