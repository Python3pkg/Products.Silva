#!/usr/bin/python
import os

# Zope
from Globals import InitializeClass

# Silva
from Products.Silva.transform.renderers.GenericXSLTRenderer import GenericXSLTRenderer

class RenderImagesOnRight(GenericXSLTRenderer):
    def __init__(self):
        self._name = 'Images on Right'
        self._stylesheet = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "images_to_the_right.xslt")

InitializeClass(RenderImagesOnRight)
