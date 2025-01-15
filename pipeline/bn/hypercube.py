from typing import Union

class Hypercube(dict):

    def __init__(self, kwargs):

        for value in kwargs.values():
            if value not in [0,1,"*"]:
                raise ValueError("value not equal to 0, 1 or *")
        super().__init__(kwargs)
    
    def update(self, other):

        if not isinstance(other, dict):
            raise TypeError(f"unsupported method types for update: '{type(self)}' and '{type(other)}'")
        elif not isinstance(other, Hypercube):
            return super().update(Hypercube(other))
        else:
            return super().update(other)
    
    def is_subhypercube(self, other):

        if not isinstance(other, dict):
            raise TypeError(f"unsupported method types for is_subhypercube: '{type(self)}' and '{type(other)}'")
        elif self.keys() != other.keys():
            raise ValueError("unsupported method values for is_subhypercube: different components")
        elif not isinstance(other, Hypercube):
            other = Hypercube(other)

        for component, value in self.items():
            other_value = other[component]
            if other_value != "*"and value != other_value:
                return False
        return True
