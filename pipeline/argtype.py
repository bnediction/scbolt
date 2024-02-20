#!/usr/bin/env python

import argparse

class Range(argparse.Action):
    
    def __init__(
        self,
        min=None,
        max=None,
        *args,
        **kwargs
    ):
        self.min = min
        self.max = max
        kwargs.update({
            "nargs":1,
            "metavar":f"[{self.min}-{self.max}]"
        })
        super(Range, self).__init__(*args, **kwargs)

    def __call__(
        self,
        parser,
        namespace,
        value,
        option_string=None
    ):
        if not (self.min <= value <= self.max):
            raise argparse.ArgumentError(self, f"value {value} not in range [{self.min}-{self.max}].")
        setattr(namespace, self.dest, value)

class Str2prefix(argparse.Action):

    def __init__(
        self,
        *args,
        **kwargs
    ):
        kwargs.update({
            "type":str,
            "metavar":"LITERAL"
        })
        super(Str2prefix, self).__init__(*args, **kwargs)

    def __call__(
        self,
        parser,
        namespace,
        value,
        option_string=None
    ):
        if value:
            value = value if value[-1] in ["-","_"] else value + "_"
        else:
            self.default
        setattr(namespace, self.dest, value)
