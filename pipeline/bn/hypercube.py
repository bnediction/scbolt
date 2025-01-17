from typing import List

class Hypercube(dict):

    def __init__(self, node_value_mapping):

        for value in node_value_mapping.values():
            if value not in [0,1,"*"]:
                raise ValueError("value not equal to 0, 1 or *")
        super().__init__(node_value_mapping)
    
    def update(self, other):

        if not isinstance(other, dict):
            raise TypeError(f"unsupported method types for update: '{type(self)}' and '{type(other)}'")
        elif not isinstance(other, Hypercube):
            return super().update(Hypercube(other))
        else:
            return super().update(other)
    
    def is_fixed_point(self):

        return False if "*" in self.values() else True
        
    def is_smaller_than(self, other):

        if not isinstance(other, dict):
            raise TypeError(f"unsupported method types for is_smaller_than: '{type(self)}' and '{type(other)}'")
        elif self.keys() != other.keys():
            raise ValueError("unsupported method values for is_smaller_than: different components")
        elif not isinstance(other, Hypercube):
            other = Hypercube(other)

        for component, value in self.items():
            other_value = other[component]
            if other_value != "*" and value != other_value:
                return False
        return True

    def is_larger_than(self, other):
        if not isinstance(other, dict):
            raise TypeError(f"unsupported method types for is_larger_than: '{type(self)}' and '{type(other)}'")
        elif self.keys() != other.keys():
            raise ValueError("unsupported method values for is_larger_than: different components")
        elif not isinstance(other, Hypercube):
            other = Hypercube(other)

        for component, value in self.items():
            other_value = other[component]
            if value != "*" and value != other_value:
                return False
        return True
    
    def smaller_hypercube_number(self, others: List):

        n = 0
        for hypercube in others:
            if self.is_smaller_than(hypercube):
                n += 1
        return n

    def larger_hypercube_number(self, others: List):

        n = 0
        for hypercube in others:
            if self.is_larger_than(hypercube):
                n += 1
        return n

class HypercubeCollection(list):

    def __init__(self, hypercube_list=None):

        if hypercube_list is None:
            super().__init__()
        elif not isinstance(hypercube_list, list):
            raise TypeError(f"unsupported type for instancing HypercubeCollection: '{type(hypercube_list)}', not {list}")
        else:
            super().__init__([hypercube if isinstance(hypercube, Hypercube) else Hypercube(hypercube) for hypercube in hypercube_list])
#        for hypercube in hypercube_list:
#            if isinstance(hypercube, Hypercube):
#                super().append(hypercube)
#            else:
#                super().append(Hypercube(hypercube))

    def append(self, other):

        if isinstance(other, dict):
            super().append(other if isinstance(other, Hypercube) else Hypercube(other))
        elif isinstance(other, list):
            for hypercube in other:
                super().append(hypercube if isinstance(other, Hypercube) else Hypercube(other))
            super().append([hypercube if isinstance(hypercube, Hypercube) else Hypercube(hypercube) for hypercube in hypercube_list])


    def are_fixed_points(self):

        fixed_points = HypercubeCollection()
        for hypercube in self:
            if hypercube.is_fixed_point():
                fixed_points.append(hypercube.copy())
        return fixed_points

    def are_smaller_than(self, other):

        if not isinstance(other, dict):
            raise TypeError(f"unsupported method types for are_smaller_than: '{type(self)}' and '{type(other)}'")
        elif not isinstance(other, Hypercube):
            other = Hypercube(other)

        smaller_hypercubes = []
        for hypercube in self:
            if hypercube.is_smaller_than(other):
                smaller_hypercubes.append(hypercube.copy())
        return smaller_hypercubes

    def are_larger_than(self, other):

        if not isinstance(other, dict):
            raise TypeError(f"unsupported method types for are_larger_than: '{type(self)}' and '{type(other)}'")
        elif not isinstance(other, Hypercube):
            other = Hypercube(other)

        larger_hypercubes = []
        for hypercube in self:
            if hypercube.is_larger_than(other):
                larger_hypercubes.append(hypercube.copy())
        return larger_hypercubes
