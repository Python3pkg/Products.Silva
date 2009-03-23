/*****************************************************************************
    *
    * Copyright (c) 2003-2005 Kupu Contributors. All rights reserved.
    *
    * This software is distributed under the terms of the Kupu
    * License. See LICENSE.txt for license text. For a list of Kupu
    * Contributors see CREDITS.txt.
    *
    *****************************************************************************/

// $Id: kupusilvainit.js 25442 2006-04-06 10:29:19Z guido $

/* SEE kupu/doc/EXTENDING.txt RE: contentfilters,
    and kupucontentfilters.js for examples */
function fixupNestedListFilter() {
    this.initialize = function(editor) {
        this.editor = editor;
    }

    this.filter = function(ownerdoc, htmlnode) {
        /* loop through <li>'s, checking for nested list items that have no content
            but a nested list.  These "empty" list items aren't selectable in kupu
            so they need to have an empty paragraph added to them.  Note: this
            empty paragraph get's removed when the document is saved.
            See https://bugs.launchpad.net/silva/+bug/101514 */
        var listitems = htmlnode.getElementsByTagName('li');
        var saved_lis = new Array();
        for (var i=0; i < listitems.length; i++) {
            var li = listitems[i];
            /*      alert('li length: ' + li.childNodes.length);
            for (var j = 0; j<li.childNodes.length;j++) {
                alert('li type: ' + li.childNodes[j].nodeName);
                }*/
            if (li.childNodes.length == 1 && 
                li.firstChild.nodeType == li.ELEMENT_NODE) {
            nodeName = li.firstChild.nodeName.toLowerCase();
            if (nodeName == 'ul' || nodeName == 'ol') {
                saved_lis.push(li);
            }
            }
        }
        var li = saved_lis.pop();
        while (li) {
            /* li is the list item containing the one nested list...
                so, add the nested list's children as siblings to
                the parent of li, and then remove li */
            nested_list = li.childNodes[0];
            while (nested_list.hasChildNodes()) {
                li.parentNode.insertBefore(nested_list.childNodes[0],
                    li);
            }
            li.parentNode.removeChild(li);
            li = saved_lis.pop();
        }
        return htmlnode;
    }
}

// XXX Port this to the default dist?
KupuEditor.prototype.afterInit = function() {
    // select the line after the first heading, if the document is correctly
    // formatted
    this.getDocument().getWindow().focus();
    var doc = this.getInnerDocument();
    var body = doc.getElementsByTagName('body')[0];
    var h = null;
    var iterator = new NodeIterator(body);
    while (h = iterator.next()) {
        if (h.nodeType == 1 && h.nodeName.toLowerCase() == 'h2') {
            var selection = this.getSelection();
            // okay, the first element node is a h2, select
            // next node, if it doesn't exist create and select
            var next = h.nextSibling;
            if (!next) {
                next = doc.createElement('p');
                next.appendChild(doc.createTextNode('\xa0'));
                body.appendChild(next);
            } else {
                var nodeName = next.nodeName.toLowerCase();
                if (nodeName == 'table') {
                    next = next.getElementsByTagName('td')[0];
                } else if (nodeName == 'ul' || nodeName == 'ol') {
                    next = next.getElementsByTagName('li')[0];
                };
            };
            selection.selectNodeContents(next);
            selection.collapse();
            /* if it's an external source, activate
               the ES tool */
            if (next.nodeName.toLowerCase() == 'div' && next.className == 'externalsource') {
                estool = kupu.getTool('extsourcetool');
                if (estool) estool.updateState(next);
            };
            break;
        } else if (h.nodeType == 1) {
            break;
        };
    };

    /* add an empty 'p' at the end of the body.  This enables content to be 
       added to the end of a doc when the last element in the doc is a table 
       or an external source. This will get stripped out when the doc is saved.
       */
    var blank = doc.createElement('p');
    blank.appendChild(doc.createTextNode('\xa0'));
    body.appendChild(blank);
    
    this.registerFilter(new fixupNestedListFilter());

    // if we don't first focus the outer window, Mozilla won't show a cursor
    window.focus();
    this.getDocument().getWindow().focus();

    // jasper@infrae.com: 2008-09-08,  FF3 Tab list re-ordering
    // make sure that the indent/outdent commands are issued when
    // the tab keys are pressed.
    var tabbing_handler = function(event){
        if (window.event) event = window.event;
        if (event.keyCode == '9') {
            /* if inside an external source, ignore 
                the tab */
            var estool = kupu.getTool('extsourcetool');
            if (!(estool && estool._insideExternalSource)) {
                if (event.shiftKey)
                    kupu.execCommand('outdent');
                else
                    kupu.execCommand('indent');
            }
            if (event.preventDefault) /* standard event model */
                event.preventDefault();
            return false; /* for IE */
        }
    }
    if (doc.addEventListener) {
        doc.addEventListener('keydown', tabbing_handler, true);
    } else if (doc.attachEvent) {
        doc.attachEvent('onkeydown', tabbing_handler);
    };
};

function initSilvaKupu(iframe) {
    // first we create a logger
    var l = new DummyLogger();

    // now some config values
    var conf = loadDictFromXML(document, 'kupuconfig');

    // the we create the document, hand it over the id of the iframe
    var doc = new KupuDocument(iframe);

    // now we can create the controller
    var kupu = new KupuEditor(doc, conf, l);
    kupu.registerContentChanger(document.getElementById('kupu-editor-textarea'));
    /* since there is only one kupu editor on a page in Silva, make the
        kupu editor available globally.  This is useful in cases where
        external code needs to set kupu.content_changed */
    window.kupueditor = kupu;

    // make that page unloads can be cancelled (if supported by the browser)
    addEventHandler(window, 'beforeunload', saveOnPart);
    var cancelEvent = function(e) {
        if (e.stopPropagation) {
            e.stopPropagation();
        } else {
            e.returnValue = false;
        };
        if (e.preventDefault){
            e.preventDefault();
        }
        return false;
    };
    // to make firefox not pop up a warning as well...
    addEventHandler(window, 'unload', cancelEvent); 

    // jasper@infrae.com: 2006-12-08,  Disabled context menu
    // var cm = new ContextMenu();
    // kupu.setContextMenu(cm);

    // now we can create a UI object which we can use from the UI
    var ui = new SilvaKupuUI('kupu-tb-styles');
    kupu.registerTool('ui', ui);

    var savebuttonfunc = function(button, editor) {editor.saveDocument()};
    var savebutton = new KupuButton('kupu-save-button', savebuttonfunc);
    kupu.registerTool('savebutton', savebutton);

    // function that returns a function to execute a button command
    var execCommand = function(cmd) {
        return function(button, editor) {
            editor.execCommand(cmd);
        };
    };

    var boldchecker = ParentWithStyleChecker(new Array('b', 'strong'),
        'font-weight', 'bold');
    var boldbutton = new KupuStateButton('kupu-bold-button', 
        execCommand('bold'),
        boldchecker,
        'kupu-bold',
        'kupu-bold-pressed');
    kupu.registerTool('boldbutton', boldbutton);

    var italicschecker = ParentWithStyleChecker(new Array('i', 'em'),
        'font-style', 'italic');
    var italicsbutton = new KupuStateButton('kupu-italic-button', 
        execCommand('italic'),
        italicschecker, 
        'kupu-italic', 
        'kupu-italic-pressed');
    kupu.registerTool('italicsbutton', italicsbutton);

    var underlinechecker = ParentWithStyleChecker(new Array('u'));
    var underlinebutton = new KupuStateButton('kupu-underline-button', 
        execCommand('underline'),
        underlinechecker,
        'kupu-underline', 
        'kupu-underline-pressed');
    kupu.registerTool('underlinebutton', underlinebutton);

    var subscriptchecker = ParentWithStyleChecker(new Array('sub'));
    var subscriptbutton = new KupuStateButton('kupu-subscript-button',
        execCommand('subscript'),
        subscriptchecker,
        'kupu-subscript',
        'kupu-subscript-pressed');
    kupu.registerTool('subscriptbutton', subscriptbutton);

    var superscriptchecker = ParentWithStyleChecker(new Array('super', 'sup'));
    var superscriptbutton = new KupuStateButton('kupu-superscript-button', 
        execCommand('superscript'),
        superscriptchecker,
        'kupu-superscript', 
        'kupu-superscript-pressed');
    kupu.registerTool('superscriptbutton', superscriptbutton);

    var undobutton = new KupuButton('kupu-undo-button', execCommand('undo'))
    kupu.registerTool('undobutton', undobutton);

    var redobutton = new KupuButton('kupu-redo-button', execCommand('redo'))
    kupu.registerTool('redobutton', redobutton);

    var listtool = new ListTool('kupu-list-ul-addbutton', 'kupu-list-ol-addbutton',
        'kupu-ulstyles', 'kupu-olstyles');
    kupu.registerTool('listtool', listtool);

    var dltool = new DefinitionListTool('kupu-list-dl-addbutton');
    kupu.registerTool('dltool', dltool);

    var toctool = new SilvaTocTool(
        'kupu-toolbox-toc-depth', 'kupu-toc-del-button',
        'kupu-toolbox-toc', 'kupu-toolbox', 'kupu-toolbox-active');
    kupu.registerTool('toctool', toctool);

    var linktool = new SilvaLinkTool();
    kupu.registerTool('linktool', linktool);
    var linktoolbox = new SilvaLinkToolBox(
        "kupu-link-input", 'kupu-linktarget-select', 'kupu-linktarget-input',
        "kupu-link-addbutton", 'kupu-link-updatebutton',
        'kupu-link-delbutton', 'kupu-toolbox-links', 'kupu-toolbox',
        'kupu-toolbox-active');
    linktool.registerToolBox("linktoolbox", linktoolbox);

    var indextool = new SilvaIndexTool(
        'kupu-index-title', 'kupu-index-name', 'kupu-index-addbutton', 
        'kupu-index-updatebutton', 'kupu-index-deletebutton', 
        'kupu-toolbox-indexes', 'kupu-toolbox', 'kupu-toolbox-active');
    kupu.registerTool('indextool', indextool);

    var extsourcetool = new SilvaExternalSourceTool(
        'kupu-toolbox-extsource-id', 'kupu-extsource-formcontainer', 
        'kupu-extsource-addbutton', 'kupu-extsource-cancelbutton',
        'kupu-extsource-updatebutton', 'kupu-extsource-delbutton',
        'kupu-toolbox-extsource', 'kupu-toolbox', 'kupu-toolbox-active',
        'kupu-extsource-enabledflag', 'kupu-extsource-disabledtext',
        'kupu-extsource-nosourcestext');
    kupu.registerTool('extsourcetool', extsourcetool);

    var citationtool = new SilvaCitationTool(
        'kupu-citation-authorinput', 'kupu-citation-sourceinput',
        'kupu-citation-addbutton', 'kupu-citation-updatebutton',
        'kupu-citation-deletebutton', 'kupu-citation-form');
    kupu.registerTool('citationtool', citationtool);

    var abbrtool = new SilvaAbbrTool('kupu-abbr-type-abbr', 'kupu-abbr-type-acronym', 
        'kupu-abbr-radiorow', 'kupu-abbr-title',
        'kupu-abbr-addbutton', 'kupu-abbr-updatebutton',
        'kupu-abbr-deletebutton', 'kupu-toolbox-abbr',
        'kupu-toolbox', 'kupu-toolbox-active');
    kupu.registerTool('abbrtool', abbrtool);

    var commentstool = new SilvaCommentsTool('kupu-toolbox-comment');
    kupu.registerTool('commentstool', commentstool);

    var imagetool = new SilvaImageTool(
        'kupu-toolbox-image-edit', 'kupu-toolbox-image-src',
        'kupu-toolbox-image-target', 'kupu-toolbox-image-target-input',
        'kupu-toolbox-image-link-checkbox-hires',
        'kupu-toolbox-image-link',
        'kupu-toolbox-image-align', 'kupu-toolbox-image-alt', 
        'kupu-toolbox-images', 'kupu-toolbox',
        'kupu-toolbox-active', 'kupu-toolbox-image-edit-button',
        'kupu-toolbox-image-link-cont');
    kupu.registerTool('imagetool', imagetool);

    var tabletool = new SilvaTableTool(); 
    kupu.registerTool('tabletool', tabletool);
    var tabletoolbox = new SilvaTableToolBox(
        'kupu-toolbox-addtable', 'kupu-toolbox-edittable', 'kupu-table-newrows',
        'kupu-table-newcols','kupu-table-makeheader', 'kupu-table-classchooser',
        'kupu-table-alignchooser', 'kupu-table-columnwidth',
        'kupu-table-addtable-button', 'kupu-table-addrow-button',
        'kupu-table-delrow-button', 'kupu-table-addcolumn-button',
        'kupu-table-delcolumn-button', 'kupu-table-fix-button',
        'kupu-table-delete-button', 'kupu-toolbox-tables', 
        'kupu-toolbox', 'kupu-toolbox-active'
        );
    tabletool.registerToolBox('tabletoolbox', tabletoolbox);

    var propertytool = new SilvaPropertyTool('propsrow', 
        'kupu-properties-form');
    kupu.registerTool('properties', propertytool);

    var showpathtool = new ShowPathTool();
    kupu.registerTool('showpathtool', showpathtool);

    var sourceedittool = new SourceEditTool('kupu-source-button',
        'kupu-editor-textarea');
    kupu.registerTool('sourceedittool', sourceedittool);

/*
    var spellchecker = new KupuSpellChecker('kupu-spellchecker-button',
        'kupu_spellcheck');
    kupu.registerTool('spellchecker', spellchecker);
*/

    var cleanupexpressions = new CleanupExpressionsTool(
        'kupucleanupexpressionselect', 'kupucleanupexpressionbutton');
    kupu.registerTool('cleanupexpressions', cleanupexpressions);

    var viewsourcetool = new ViewSourceTool();
    kupu.registerTool('viewsourcetool', viewsourcetool);

    // Function that returns function to open a drawer
    var opendrawer = function(drawerid) {
        return function(button, editor) {
            drawertool.openDrawer(drawerid);
        };
    };

    /*
    var imagelibdrawerbutton = new KupuButton('kupu-imagelibdrawer-button',
        opendrawer('imagelibdrawer'));
    kupu.registerTool('imagelibdrawerbutton', imagelibdrawerbutton);

    var linklibdrawerbutton = new KupuButton('kupu-linklibdrawer-button',
        opendrawer('linklibdrawer'));
    kupu.registerTool('linklibdrawerbutton', linklibdrawerbutton);
    */

    // create some drawers, drawers are some sort of popups that appear when a 
    // toolbar button is clicked
    var drawertool = new DrawerTool();
    kupu.registerTool('drawertool', drawertool);

    /*
    var linklibdrawer = new LinkLibraryDrawer(linktool, conf['link_xsl_uri'],
        conf['link_libraries_uri'],
        conf['link_images_uri']);
    drawertool.registerDrawer('linklibdrawer', linklibdrawer);

    var imagelibdrawer = new ImageLibraryDrawer(imagetool, conf['image_xsl_uri'],
        conf['image_libraries_uri'],
        conf['search_images_uri']);
    drawertool.registerDrawer('imagelibdrawer', imagelibdrawer);
    */

//    var nonxhtmltagfilter = new NonXHTMLTagFilter();
//    kupu.registerFilter(nonxhtmltagfilter);

    kupu.xhtmlvalid.setAttrFilter(['is_toc', 'toc_depth', 'is_citation', 
        'source', 'author', 'source_id', 'source_title', 'key',
        'silva_type', 'alignment', 
        'link_to_hires', 'link', 'silva_src',
        'silva_href', 'silva_column_info']);
    // allow all attributes on div, since ExternalSources require that
    kupu.xhtmlvalid.includeTagAttributes(['div'], ['*']);
    kupu.xhtmlvalid.includeTagAttributes(['span'], ['key']);
    kupu.xhtmlvalid.includeTagAttributes(['p'], ['silva_type']);
    kupu.xhtmlvalid.includeTagAttributes(['h6'], ['silva_type']);
    kupu.xhtmlvalid.includeTagAttributes(['img'], ['alignment', 
        'link_to_hires', 
        'target', 'link',
        'silva_src']);
    kupu.xhtmlvalid.includeTagAttributes(['a'], ['silva_href']);
    kupu.xhtmlvalid.includeTagAttributes(['table'], ['silva_column_info']);

    if (window.kuputoolcollapser) {
        var collapser = new window.kuputoolcollapser.Collapser(
            'kupu-toolboxes');
        collapser.initialize();
    };

    // have to set a blacklist of tags for div, since IE will otherwise
    // save every possible HTML attr for the div
    kupu.xhtmlvalid.excludeTagAttributes(['div'], ['onrowexit', 'onfocusout',
        'onrowsinserted', 'disabled', 'oncopy', 'onresizestart',
        'onerrorupdate', 'tabIndex', 'ondeactivate', 
        'ondataavailable', 'ondragover', 'title', 'accessKey', 
        'onkeypress', 'dataFld', 'onmousemove', 'onactivate',
        'onafterupdate', 'ondrag', 'contentEditable', 'hideFocus',
        'onblur', 'onmouseout', 'oncellchange', 'onmouseleave',
        'onkeydown', 'dataSrc', 'onmousewheel', 'onpaste', 'ondrop',
        'onrowsdelete', 'onrowenter', 'ondragend', 'align', 
        'onlayoutcomplete', 'onbeforedeactivate', 'nofocusrect',
        'ondblclick', 'onselectstart', 'onreadystatechange',
        'dataFormatAs', 'onmousedown', 'onscroll', 'style',
        'implementation', 'onbeforecut', 'oncontrolselect',
        'ondatasetcomplete', 'onmouseup', 'noWrap', 'onfocusin',
        'onresizeend', 'oncontextmenu', 'ondragstart', 'onmoveend',
        'onbeforeeditfocus', 'onpropertychange', 'lang', 
        'onmovestart', 'onkeyup', 'dir', 'onfilterchange',
        'onmouseenter', 'onresize', 'onclick', 'onbeforecopy',
        'onfocus', 'ondatasetchanged', 'id', 'onmove', 'onpage',
        'ondragenter', 'ondragleave', 'oncut', 'onbeforedeactivate',
        'onhelp', 'onlosecapture', 'onbeforeupdate', 'onmouseover',
        'onbeforeactivate', 'onbeforepaste']);

    return kupu;
};

function initSilvaPopupKupu(iframe) {
    // first we create a logger
    var l = new DummyLogger();

    // now some config values
    var conf = loadDictFromXML(document, 'kupuconfig');

    // the we create the document, hand it over the id of the iframe
    var doc = new KupuDocument(iframe);

    // now we can create the controller
    var kupu = new KupuEditor(doc, conf, l);

    kupu.registerContentChanger(document.getElementById('kupu-editor-textarea'));

    var cancelEvent = function(e) {
        if (e.stopPropagation) {
            e.stopPropagation();
        } else {
            e.returnValue = false;
        };
        if (e.preventDefault){
            e.preventDefault();
        }
        return false;
    };
    // to make firefox not pop up a warning as well...
    addEventHandler(window, 'unload', cancelEvent); 

    // jasper@infrae.com: 2006-12-08,  Disabled context menu
    // var cm = new ContextMenu();
    // kupu.setContextMenu(cm);

    // now we can create a UI object which we can use from the UI
    var ui = new SilvaKupuUI('kupu-tb-styles');
    kupu.registerTool('ui', ui);

    var savebuttonfunc = function(button, editor) {saveKupuPopup(editor)};
    var savebutton = new KupuButton('kupu-save-button', savebuttonfunc);
    kupu.registerTool('savebutton', savebutton);

    // function that returns a function to execute a button command
    var execCommand = function(cmd) {
        return function(button, editor) {
            editor.execCommand(cmd);
        };
    };

    var boldchecker = ParentWithStyleChecker(new Array('b', 'strong'),
        'font-weight', 'bold');
    var boldbutton = new KupuStateButton('kupu-bold-button', 
        execCommand('bold'),
        boldchecker,
        'kupu-bold',
        'kupu-bold-pressed');
    kupu.registerTool('boldbutton', boldbutton);

    var italicschecker = ParentWithStyleChecker(new Array('i', 'em'),
        'font-style', 'italic');
    var italicsbutton = new KupuStateButton('kupu-italic-button', 
        execCommand('italic'),
        italicschecker, 
        'kupu-italic', 
        'kupu-italic-pressed');
    kupu.registerTool('italicsbutton', italicsbutton);

    var underlinechecker = ParentWithStyleChecker(new Array('u'));
    var underlinebutton = new KupuStateButton('kupu-underline-button', 
        execCommand('underline'),
        underlinechecker,
        'kupu-underline', 
        'kupu-underline-pressed');
    kupu.registerTool('underlinebutton', underlinebutton);

    var subscriptchecker = ParentWithStyleChecker(new Array('sub'));
    var subscriptbutton = new KupuStateButton('kupu-subscript-button',
        execCommand('subscript'),
        subscriptchecker,
        'kupu-subscript',
        'kupu-subscript-pressed');
    kupu.registerTool('subscriptbutton', subscriptbutton);

    var superscriptchecker = ParentWithStyleChecker(new Array('super', 'sup'));
    var superscriptbutton = new KupuStateButton('kupu-superscript-button', 
        execCommand('superscript'),
        superscriptchecker,
        'kupu-superscript', 
        'kupu-superscript-pressed');
    kupu.registerTool('superscriptbutton', superscriptbutton);

    var undobutton = new KupuButton('kupu-undo-button', execCommand('undo'))
    kupu.registerTool('undobutton', undobutton);

    var redobutton = new KupuButton('kupu-redo-button', execCommand('redo'))
    kupu.registerTool('redobutton', redobutton);

    var listtool = new ListTool('kupu-list-ul-addbutton', 'kupu-list-ol-addbutton',
        'kupu-ulstyles', 'kupu-olstyles');
    kupu.registerTool('listtool', listtool);

    var dltool = new DefinitionListTool('kupu-list-dl-addbutton');
    kupu.registerTool('dltool', dltool);

    var linktool = new SilvaLinkTool();
    kupu.registerTool('linktool', linktool);
    var linktoolbox = new SilvaLinkToolBox(
        "kupu-link-input", 'kupu-linktarget-select', 'kupu-linktarget-input',
        "kupu-link-addbutton", 'kupu-link-updatebutton',
        'kupu-link-delbutton', 'kupu-toolbox-links', 'kupu-toolbox',
        'kupu-toolbox-active');
    linktool.registerToolBox("linktoolbox", linktoolbox);

    var indextool = new SilvaIndexTool(
        'kupu-index-title', 'kupu-index-name', 'kupu-index-addbutton', 
        'kupu-index-updatebutton', 'kupu-index-deletebutton', 
        'kupu-toolbox-indexes', 'kupu-toolbox', 'kupu-toolbox-active');
    kupu.registerTool('indextool', indextool);

    var abbrtool = new SilvaAbbrTool('kupu-abbr-type-abbr', 'kupu-abbr-type-acronym', 
        'kupu-abbr-radiorow', 'kupu-abbr-title',
        'kupu-abbr-addbutton', 'kupu-abbr-updatebutton',
        'kupu-abbr-deletebutton', 'kupu-toolbox-abbr',
        'kupu-toolbox', 'kupu-toolbox-active');
    kupu.registerTool('abbrtool', abbrtool);

    var showpathtool = new ShowPathTool();
    kupu.registerTool('showpathtool', showpathtool);

    var sourceedittool = new SourceEditTool('kupu-source-button',
        'kupu-editor-textarea');
    kupu.registerTool('sourceedittool', sourceedittool);

    var cleanupexpressions = new CleanupExpressionsTool(
        'kupucleanupexpressionselect', 'kupucleanupexpressionbutton');
    kupu.registerTool('cleanupexpressions', cleanupexpressions);

    var viewsourcetool = new ViewSourceTool();
    kupu.registerTool('viewsourcetool', viewsourcetool);

    // Function that returns function to open a drawer
    var opendrawer = function(drawerid) {
        return function(button, editor) {
            drawertool.openDrawer(drawerid);
        };
    };

    kupu.xhtmlvalid.setAttrFilter(['is_toc', 'toc_depth', 'is_citation', 
        'source', 'author', 'source_id', 'source_title', 'key',
        'silva_type', 'alignment', 
        'link_to_hires', 'link', 'silva_src',
        'silva_href', 'silva_column_info']);
    // allow all attributes on div, since ExternalSources require that
    kupu.xhtmlvalid.includeTagAttributes(['div'], ['*']);
    kupu.xhtmlvalid.includeTagAttributes(['span'], ['key']);
    kupu.xhtmlvalid.includeTagAttributes(['p'], ['silva_type']);
    kupu.xhtmlvalid.includeTagAttributes(['h6'], ['silva_type']);
    kupu.xhtmlvalid.includeTagAttributes(['img'], ['alignment', 
        'link_to_hires', 
        'target', 'link',
        'silva_src']);
    kupu.xhtmlvalid.includeTagAttributes(['a'], ['silva_href']);
    kupu.xhtmlvalid.includeTagAttributes(['table'], ['silva_column_info']);

    if (window.kuputoolcollapser) {
        var collapser = new window.kuputoolcollapser.Collapser(
            'kupu-toolboxes');
        collapser.initialize();
    };

    // have to set a blacklist of tags for div, since IE will otherwise
    // save every possible HTML attr for the div
    kupu.xhtmlvalid.excludeTagAttributes(['div'], ['onrowexit', 'onfocusout',
        'onrowsinserted', 'disabled', 'oncopy', 'onresizestart',
        'onerrorupdate', 'tabIndex', 'ondeactivate', 
        'ondataavailable', 'ondragover', 'title', 'accessKey', 
        'onkeypress', 'dataFld', 'onmousemove', 'onactivate',
        'onafterupdate', 'ondrag', 'contentEditable', 'hideFocus',
        'onblur', 'onmouseout', 'oncellchange', 'onmouseleave',
        'onkeydown', 'dataSrc', 'onmousewheel', 'onpaste', 'ondrop',
        'onrowsdelete', 'onrowenter', 'ondragend', 'align', 
        'onlayoutcomplete', 'onbeforedeactivate', 'nofocusrect',
        'ondblclick', 'onselectstart', 'onreadystatechange',
        'dataFormatAs', 'onmousedown', 'onscroll', 'style',
        'implementation', 'onbeforecut', 'oncontrolselect',
        'ondatasetcomplete', 'onmouseup', 'noWrap', 'onfocusin',
        'onresizeend', 'oncontextmenu', 'ondragstart', 'onmoveend',
        'onbeforeeditfocus', 'onpropertychange', 'lang', 
        'onmovestart', 'onkeyup', 'dir', 'onfilterchange',
        'onmouseenter', 'onresize', 'onclick', 'onbeforecopy',
        'onfocus', 'ondatasetchanged', 'id', 'onmove', 'onpage',
        'ondragenter', 'ondragleave', 'oncut', 'onbeforedeactivate',
        'onhelp', 'onlosecapture', 'onbeforeupdate', 'onmouseover',
        'onbeforeactivate', 'onbeforepaste']);

    return kupu;
};

/* kupu silva popup window's "save" method
    -- it's similar to kupumultieditor's prepareForm function
        in that it's a direct copy, with some customizations
        to write the content back to the caller */
function saveKupuPopup(editor) {
    /* add some fields to the form and place the contents of the iframes 
    */
    var sourcetool = editor.getTool('sourceedittool');
    if (sourcetool) {sourcetool.cancelSourceMode();};

    // make sure people can't edit or save during saving
    if (!editor._initialized) {
        return;
    }
    editor._initialized = false;

    // set the window status so people can see we're actually saving
    parent.status= _("Please wait while saving document...");

    // call (optional) beforeSave() method on all tools
    for (var tid in editor.tools) {
        var tool = editor.tools[tid];
        if (tool.beforeSave) {
            try {
                tool.beforeSave();
            } catch(e) {
                alert(e);
                editor._initialized = true;
                return;
            };
        };
    };

    editor.logMessage(_("Cleanup done, sending document to server"));
    // pass the content through the filters
    editor.logMessage(_("Starting HTML cleanup"));
    var transform = editor._filterContent(editor.getInnerDocument().documentElement);

    // XXX need to fix this.  Sometimes a spurious "\n\n" text 
    // node appears in the transform, which breaks the Moz 
    // serializer on .xml
    var contents =  editor._serializeOutputToString(transform);
    editor.logMessage(_("Cleanup done, sending back to opening window"));
    var to_caller = contents.substring(contents.search('<body>')+6,
        contents.search('</body>'));
    window.opener.save_callback(to_caller);
    window.close();
};
