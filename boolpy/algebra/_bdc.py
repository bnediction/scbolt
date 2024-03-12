#!/usr/bin/env python

from typing import Union
from .._boolean import PartialBoolean

import math

class BooleanDifferentialCalculus(object):

    def __init__(self) -> None:
        pass

    def __conversion__(self, value):
        if isinstance(value, bool):
            return PartialBoolean(value)
        if isinstance(value, float):
            if value in [0., 1.] or math.isnan(value):
                return PartialBoolean(value)
            else:
                raise TypeError(f"incorrect conversion for {value}")
        elif isinstance(value, PartialBoolean):
            return value
        else:
            raise TypeError(f"incorrect conversion for {value}")

    def differential(self, v1, v2) -> Union[-1, 0, 1]:
        _v1 = self.__conversion__(v1)
        _v2 = self.__conversion__(v2)
        if _v1 == _v2:
            return 0
        elif _v1 < _v2:
            return 1
        elif _v1 > _v2:
            return -1
    
    def successor_test_from_pair(self, source_v1, source_v2, target_v1, target_v2, sign) -> Union[-1, 0, 1]:
        _source_v1 = self.__conversion__(source_v1)
        _source_v2 = self.__conversion__(source_v2)
        _target_v1 = self.__conversion__(target_v1)
        _target_v2 = self.__conversion__(target_v2)
        source_differential = self.differential(_source_v1, _source_v2)
        target_differential = self.differential(_target_v1, _target_v2)
        if sign not in [-1, 1]:
            raise ValueError(f"`sign` does not take value in [-1, 1]: {sign}")
        if target_differential == 0:
            return 0
        elif source_differential == 0:
            if _source_v1 == _source_v2 == PartialBoolean(1):
                return 1 if sign == target_differential else -1
            if _source_v1 == _source_v2 == PartialBoolean(0):
                return -1 if sign == target_differential else 1
            if _source_v1 == _source_v2 == PartialBoolean(float("nan")):
                return 0
        elif source_differential != 0:
            return 0
        else:
            raise AssertionError("incoherence when assessing which condition is successor")
