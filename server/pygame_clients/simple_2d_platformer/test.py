"""
 -------------------------------------------------------------------------
 shine - 
 test
 
 !!TODO: add file description here!! 
  
 created: 2017/04/19 in PyCharm
 (c) 2017 Sven - ducandu GmbH
 -------------------------------------------------------------------------
"""

import types


class Component(object):
    def __init__(self, name):
        self.name = name
        self.game_object = None  # to be set by Entity when this component gets added

    def added(self):
        self.extend(self.extension)

    # extends the given method (has to take self as 1st param) onto the GameObject, so that this method can be called
    # directly from the GameObject
    def extend(self, method: callable):
        # use the MethodType function to bind the play_animation function to only this object (not any other instances of the GameObject's class)
        setattr(self.game_object, method.__name__, types.MethodType(method, self.game_object))

    def extension(comp, obj, param1):
        print("inside awesome extension: comp: {} obj: {} param1: {}!".format(type(comp).__name__, type(obj).__name__, str(param1)))


class GameObject(object):
    def __init__(self):
        self.components = {}  # dict of added components by component's name

    def add_component(self, component):
        component.game_object = self
        self.components[component.name] = component
        component.added()



a = GameObject()
b = Component("comp")
a.add_component(b)
print("done!")

