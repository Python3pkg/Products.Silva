"""
module for conversion from current 

   RealObjects' 2.11 Pseudo-HTML 
   
       to

   silva (0.8.5) 

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
__version__='$Revision: 1.14 $'

try:
    from transform.base import Element, Text, Frag
except ImportError:
    from Products.Silva.transform.base import Element, Text, Frag

import silva

DEBUG=0

def move_h5_into_list(self):
    """ tries to find h5-tags in front of html lists 
        and puts them into the html list tag if it finds a h5.  
        a moved h5 has a 'moved' attribute so that it doesn't get
        moved again. 
    """
    for pre, tag, post in self.find_all_partitions(tag=('ul','ol')):
        h5 = pre.find('h5')

        h5 = h5 and h5[-1]
        container = self.content

        if not h5 or hasattr(h5, 'moved'):
            if not self._matches( ('ul','ol')):
                continue
            li = pre.find('li')
            if li:
                h5 = li[-1].find('h5')
                h5 = h5 and h5[-1]
                container = li[-1].content

        if h5 and not hasattr(h5, 'moved'):
            h5 = container.pop(container.index(h5))
            h5.moved = 1
            tag.content.insert(0,h5)
            #print "moved h5=",h5.asBytes(), "into", tag.asBytes()#name()

class html(Element):
    def convert(self, context, *args, **kwargs):
        """ forward to the body element ... """
        bodytag = self.find('body')[0]
        return bodytag.convert(context, *args, **kwargs)

class head(Element):
    def convert(self, context, *args, **kwargs):
        """ ignore """
        return u''

class body(Element):
    "html-body element"
    def convert(self, context, *args, **kwargs):
        """ contruct a silva_document with id and title
            either from information found in the html-nodes 
            or from the context (where silva should have
            filled in title and id as key/value pairs)
        """
        move_h5_into_list(self)
        h2_tag = self.find(tag=h2)
        if not h2_tag:
            rest = self.find()
            title, id = context['title'], context['id']
        else:
            h2_tag=h2_tag[0]
            title = h2_tag.content
            rest = self.find(ignore=h2_tag.__eq__) 
            id = h2_tag.attrs.get('silva_id') or context['id']

        return silva.silva_document(
                silva.title(title),
                silva.doc(
                    rest.convert(context, *args, **kwargs)
                ),
                id = id
            )

class h1(Element):
    def convert(self, *args, **kwargs):
        return silva.heading(
            self.content.convert(*args, **kwargs),
            type='normal'
        )

class h2(Element):
    ""
    def convert(self, *args, **kwargs):
        return silva.heading(
            self.content.convert(*args, **kwargs),
            type="normal"
            )

class h3(Element):
    ""
    def convert(self, *args, **kwargs):
        return silva.heading(
            self.content.convert(*args, **kwargs),
            type="normal"
            )

class h4(Element):
    ""
    def convert(self, *args, **kwargs):
        return silva.heading(
            self.content.convert(*args, **kwargs),
            type="sub"
            )

class h5(Element):
    """ List heading """
    def convert(self, context, *args, **kwargs):
        """ return a normal heading. note that the h5-to-title
            conversion is done by the html list-tags themselves. 
            Thus h5.convert is only called if there is no
            list context and therefore converted to a subheading.
        """
        return silva.heading(
            self.content.convert(context, *args, **kwargs),
            type="sub",
            )

class h6(Element):
    def convert(self, *args, **kwargs):
        """ this only gets called if the user erroronaously
            used h6 somewhere 
        """
        return silva.heading(
            self.content.convert(*args, **kwargs),
            type="sub",
            )

class p(Element):
    """ the html p element can contain nodes which are "standalone"
        in silva-xml. 
    """
    def convert(self, *args, **kwargs):
        pre,img,post = self.find_and_partition('img')
        type = self.attrs.get('silva_type', None)
        if pre:
            pre = silva.p(pre.convert(*args, **kwargs), type=type)
        if img:
            img = img.convert(*args, **kwargs)
        if post:
            post = silva.p(post.convert(*args, **kwargs), type=type)

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
        they may come from nlist,dlist,list, their title 
        may be outside the ul/ol tag, there are lots of different
        types and the silva and html type names are different. 

        this implementation currently is a bit hackish.
    """
    default_types = ('disc','circle','square','none')

    def convert(self, *args, **kwargs):
        move_h5_into_list(self)

        if self.is_dlist():
            return self.convert_dlist(*args, **kwargs)
        elif self.is_nlist():
            return self.convert_nlist(*args, **kwargs)
        else:
            return self.convert_list(*args, **kwargs)

    def is_nlist(self):
        for i in self.find(ignore=lambda x: x.name()=='h5').compact():
            if i.name()!='li':
                return 1

    def convert_list(self, *args, **kwargs):
        type = self.get_type()

        h5, title = self.get_title(*args, **kwargs)
        ignorefunc= h5 and h5.__eq__ or None

        return silva.list(
            title,
            self.find(ignore=ignorefunc).convert(*args, **kwargs),
            type=type
        )


    def convert_nlist(self, *args, **kwargs):

        type = self.get_type()
        h5, title = self.get_title(*args, **kwargs)
        ignorefunc= h5 and h5.__eq__ or None

        #res = silva.nlist(
        #    title,
        #    self.find(ignore=ignorefunc).convert(*args, **kwargs),
        ##    type=type
        #)

        lastli = None
        content = Frag()
        for tag in self.find(ignore=ignorefunc).convert(*args, **kwargs):
            name = tag.name()
            if name == 'li':
                lastli = tag
                tag.content = silva.mixin_paragraphs(tag.content)
            elif name != 'title' and tag.compact():
                if not lastli:
                    tag = silva.li(tag)
                else:
                    lastli.content.append(tag)
                    lastli = None
                    continue
            content.append(tag)

        return silva.nlist(
            title,
            content,
            type=type)
                    

        # corrections to the resulting xml 
        lastli = None
        for count in xrange(len(res.content)):
            tag = res.content[count]
            if tag.name()=='title':
                continue
            elif tag.name()=='li':
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
        if type is None:
            type = self.attrs.get('silva_type')
        else:
            type = type.content.lower()

        if type not in self.default_types:
            type = self.default_types[0]
        return type

    def get_title(self, *args, **kwargs):
        h5_tag = self.find(tag=h5)
        #print "found h5 in", self.name(), ":", h5_tag.asBytes()
        if not h5_tag:
            li = self.find('li')
            if li:
                li = li[0]
                h5_tag = li.find('h5')
                if h5_tag:
                    h5_tag = h5_tag[0]
                    li.content.remove(h5_tag)
                    if not li.extract_text().strip():
                        self.content.remove(li)
                    return h5_tag, silva.title(h5_tag.content.convert(*args, **kwargs))
            return None, silva.title()
        else:
            return h5_tag[0], silva.title(h5_tag[0].content.convert(*args, **kwargs))

    def is_dlist(self, *args, **kwargs):
        for item in self.find('li'):
            font = item.find('font')
            if len(font)>0 and font[0].attrs.get('color')=='green':
                return 1
        
    def convert_dlist(self, *args, **kwargs):
        tags = []
        h5, title = self.get_title(*args, **kwargs)
        for item in self.find('li'):
            pre,font,post = item.find_and_partition('font')
            if font and font.attrs['color']=='green':
                tags.append(silva.dt(font.content.convert(*args,**kwargs)))
            else:
                tags.append(silva.dt())

            if post:
                try: 
                    post[0].content = post[0].content.lstrip()
                except AttributeError:
                    pass

            tags.append(silva.dd(post.convert(*args, **kwargs)))

        return silva.dlist(
            title,
            type='normal',
            *tags
            )



class ol(ul):
    default_types = ('1','a','i')

class li(Element):
    def convert(self, *args, **kwargs):
        move_h5_into_list(self)

        return silva.li(
            self.content.convert(*args, **kwargs),
            )

class b(Element):
    def convert(self, *args, **kwargs):
        return silva.strong(
            self.content.convert(*args, **kwargs),
            )

class i(Element):
    def convert(self, *args, **kwargs):
        return silva.em(
            self.content.convert(*args, **kwargs),
            )

class u(Element):
    def convert(self, *args, **kwargs):
        return silva.underline(
            self.content.convert(*args, **kwargs),
            )

class font(Element):
    def convert(self, *args, **kwargs):
        color = self.attrs.get('color')
        tag = {'aqua': silva.super, 
               'green': silva.dt,
               'blue': silva.sub,
               }.get(color)
        if tag:
            return tag(
                self.content.convert(*args, **kwargs)
            )
        else:
            return self.content.convert(*args, **kwargs)

class a(Element):
    def convert(self, *args, **kwargs):
        return silva.link(
            self.content.convert(*args, **kwargs),
            url=self.attrs['href']
            )

class img(Element):
    def convert(self, *args, **kwargs):
        from urlparse import urlparse
        src = self.attrs['src'].content
        src = urlparse(src)[2]
        if src.endswith('/image'):
            src = src[:-len('/image')]
        return silva.image(
            self.content.convert(*args, **kwargs),
            image_path=src
            )

class br(Element):
    def convert(self, *args, **kwargs):
        return silva.p(
            "",
            type='normal'
            )

class pre(Element):
    def compact(self):
        return self

    def convert(self, *args, **kwargs):
        return silva.pre(
            self.content.convert(*args, **kwargs)
        )

class table(Element):
    def convert(self, context, *args, **kwargs):
        rows = self.content.find('tr')
        if len(rows)>0:
            cols = len(rows[0].find('td'))
        return silva.table(
                self.content.convert(context, *args, **kwargs),
                columns=self.attrs.get('cols', cols),
                column_info = self.attrs.get('silva_column_info'),
                type=self.attrs.get('silva_type')
            )

class tr(Element):
    def convert(self, context, *args, **kwargs):
        return silva.row(
            self.content.convert(context, *args, **kwargs)
        )

class td(Element):
    def convert(self, *args, **kwargs):
        return silva.field(
            self.content.convert(*args, **kwargs)
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
