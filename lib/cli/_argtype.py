#!/usr/bin/env python

from typing import (
    Union,
    Sequence,
    cast,
)
from pathlib import Path
from datetime import date

import math
import re
import shutil
import textwrap

import argparse


class HelpFormatter(argparse.HelpFormatter):
    """Wrap argparse help while preserving explicit line breaks."""

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        kwargs.setdefault("max_help_position", 4)
        kwargs.setdefault(
            "width",
            min(shutil.get_terminal_size((100, 24)).columns, 100),
        )
        super().__init__(*args, **kwargs)

    def _expand_help(
        self,
        action,
    ):
        text = super()._expand_help(action)
        if not text:
            return text
        return text[0].upper() + text[1:]

    def _split_lines(
        self,
        text,
        width,
    ):
        text = textwrap.dedent(text)
        lines = []
        for line in text.splitlines():
            if line:
                lines.extend(
                    textwrap.wrap(
                        line,
                        width,
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                )
            else:
                lines.append("")
        return lines

    def _fill_text(
        self,
        text,
        width,
        indent,
    ):
        text = textwrap.dedent(text).strip("\n")
        lines = []
        for line in text.splitlines():
            if line:
                lines.extend(
                    textwrap.wrap(
                        line,
                        width,
                        initial_indent=indent,
                        subsequent_indent=indent,
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                )
            else:
                lines.append("")
        return "\n".join(lines)


def Memory(value: str) -> Union[str, None]:
    value = value.strip()
    if value == "":
        return None

    if re.fullmatch(r"[0-9]+", value):
        if int(value) <= 0:
            raise argparse.ArgumentTypeError(
                f"expected positive memory size but received {value}"
            )
        return f"{value}GB"

    memory_match = re.fullmatch(
        r"(?P<size>[0-9]+([.][0-9]+)?)\s*(KB|MB|GB|TB|KiB|MiB|GiB|TiB)",
        value,
        flags=re.IGNORECASE,
    )
    if memory_match is not None:
        if float(memory_match.group("size")) <= 0:
            raise argparse.ArgumentTypeError(
                f"expected positive memory size but received {value}"
            )
        return value

    raise argparse.ArgumentTypeError(
        "expected positive memory size; integers are interpreted as GB, "
        "or use unit KB, MB, GB, TB, KiB, MiB, GiB or TiB"
    )


class Store_version(argparse.Action):

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        self.allow_current = kwargs.pop("allow_current", True)
        self.allow_bundled = kwargs.pop("allow_bundled", False)
        self.allow_date = kwargs.pop("allow_date", True)
        self.allow_path = kwargs.pop("allow_path", False)
        default = kwargs["default"] if "default" in kwargs else None
        values = ["latest"]
        if self.allow_current:
            values.insert(0, "current")
        if self.allow_bundled:
            values.insert(0, "bundled")
        if self.allow_date:
            values.append("YYYY-MM-DD")
        if self.allow_path:
            values.append("FILE")
        kwargs.update(
            {
                "type": str,
                "metavar": f"[{' | '.join(values)}]",
                "default": default,
                "help": (
                    kwargs["help"]
                    if "help" in kwargs
                    else f"database version (default: {default})"
                ),
            }
        )
        super(Store_version, self).__init__(*args, **kwargs)

    def __call__(
        self,
        parser,
        namespace,
        value,
        option_string=None,
    ):
        value = value.strip()
        normalized_value = value.lower()

        if normalized_value == "current" and self.allow_current:
            setattr(namespace, self.dest, normalized_value)
            return

        if normalized_value == "bundled" and self.allow_bundled:
            setattr(namespace, self.dest, normalized_value)
            return

        if normalized_value == "latest":
            setattr(namespace, self.dest, normalized_value)
            return

        if self.allow_date and (
            re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)
            or re.fullmatch(r"[0-9]{8}", value)
        ):
            try:
                self._validate_date(value)
            except ValueError as error:
                raise argparse.ArgumentError(
                    self,
                    f"invalid database version date: {value}",
                ) from error
            setattr(namespace, self.dest, value)
            return

        if self.allow_path and Path(value).expanduser().exists():
            setattr(namespace, self.dest, value)
            return

        raise argparse.ArgumentError(
            self,
            self._error_message(),
        )

    def _error_message(self):
        labels = []
        if self.allow_bundled:
            labels.append("'bundled'")
        if self.allow_current:
            labels.append("'current'")
        labels.append("'latest'")
        if self.allow_date:
            labels.append("a date formatted as YYYY-MM-DD")
        if self.allow_path:
            labels.append("an existing file")
        return "expected " + ", ".join(labels)

    @staticmethod
    def _validate_date(value):
        date_parts = re.fullmatch(
            r"([0-9]{4})-?([0-9]{2})-?([0-9]{2})",
            value,
        )
        if date_parts is None:
            return
        date(*(int(part) for part in date_parts.groups()))


class Range(argparse.Action):

    def __init__(
        self,
        min: Union[float, int, None] = None,
        max: Union[float, int, None] = None,
        *args,
        **kwargs,
    ):
        min = -math.inf if min is None else min
        max = math.inf if max is None else max

        if min > max:
            raise argparse.ArgumentError(
                self,
                f"invalid values for 'min' and 'max': min must be inferior to max, but received min={min} and max={max}",
            )

        self.min = min
        self.max = max
        kwargs.update({"nargs": None, "metavar": f"[{self.min}-{self.max}]"})
        super(Range, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        if not (self.min <= value <= self.max):
            raise argparse.ArgumentError(
                self, f"value {value} not in range [{self.min}-{self.max}]"
            )
        setattr(namespace, self.dest, value)


class Min_and_max(argparse.Action):

    def __init__(
        self,
        type: type = float,
        min: Union[float, int] = -math.inf,
        max: Union[float, int] = math.inf,
        allowed_none: bool = True,
        *args,
        **kwargs,
    ):

        if min > max:
            raise argparse.ArgumentError(
                self,
                f"invalid values for 'min' and 'max': min must be inferior to max, but received min={min} and max={max}",
            )
        if type not in [float, int]:
            raise argparse.ArgumentError(
                self,
                f"invalid value for 'type': expected {float} or {int}, but received {type}",
            )

        self.min = min
        self.max = max
        self.allowed_none = allowed_none
        self.to_type = type
        kwargs.update(
            {
                "nargs": 2,
                "type": str,
                "metavar": "INT" if self.to_type is int else "FLOAT",
            }
        )
        if "default" not in kwargs:
            kwargs["default"] = [self.min, self.max]
        super(Min_and_max, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        values = cast(Sequence[str], values)

        def convert(self, value):
            if value.lower() == "none":
                if self.allowed_none is True:
                    return None
                else:
                    raise argparse.ArgumentTypeError(
                        self, f"expected {self.to_type}, but received {None}"
                    )
            elif value.lower() == "inf":
                return math.inf
            elif value.lower() == "-inf":
                return -math.inf
            else:
                return self.to_type(value)

        checked_values = []
        for i in range(2):
            v = convert(self, values[i])
            if v is not None and not isinstance(v, str):
                if not self.min <= v <= self.max:
                    raise argparse.ArgumentTypeError(
                        self,
                        f"expected values between {self.min} and {self.max}, but received {v}",
                    )
            checked_values.append(v)
        if not any(v is None or isinstance(v, str) for v in checked_values):
            checked_values.sort()
        else:
            if checked_values[0] is None:
                checked_values[0] = self.min
            if checked_values[1] is None:
                checked_values[1] = self.max

        setattr(namespace, self.dest, checked_values)


class Str_or_min_and_max(argparse.Action):

    def __init__(
        self,
        strings: Union[str, Sequence[str]],
        type: type = float,
        min: Union[float, int] = -math.inf,
        max: Union[float, int] = math.inf,
        allowed_none: bool = True,
        *args,
        **kwargs,
    ):

        if min > max:
            raise argparse.ArgumentError(
                self,
                f"invalid values for 'min' and 'max': min must be inferior to max, but received min={min} and max={max}",
            )
        if type not in [float, int]:
            raise argparse.ArgumentError(
                self,
                f"invalid value for 'type': expected {float} or {int}, but received {type}",
            )

        self.min = min
        self.max = max
        if isinstance(strings, str):
            self.strings = [strings]
        elif isinstance(strings, list):
            for s in strings:
                if not isinstance(s, str):
                    raise argparse.ArgumentTypeError(
                        self,
                        f"unsupported argument type for an element in 'strings': expected '{str}' but received '{type(s)}'",
                    )
            self.strings = strings
        else:
            raise argparse.ArgumentTypeError(
                self,
                f"unsupported argument type for 'strings': expected '{list}' or '{str} but received '{type(strings)}'",
            )
        self.allowed_none = allowed_none
        self.to_type = type
        kwargs.update(
            {
                "nargs": "+",
                "type": str,
                "metavar": (
                    "INT | LITERAL" if self.to_type is int else "FLOAT | LITERAL"
                ),
            }
        )
        if "default" not in kwargs:
            kwargs["default"] = [self.min, self.max]
        super(Str_or_min_and_max, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        values = cast(Sequence[str], values)

        def convert(self, value):
            if value.lower() == "none":
                if self.allowed_none is True:
                    return None
                else:
                    raise argparse.ArgumentTypeError(
                        self, f"expected {self.to_type}, but received {None}"
                    )
            elif value.lower() == "inf":
                return math.inf
            elif value.lower() == "-inf":
                return -math.inf
            else:
                return self.to_type(value)

        checked_values = []
        if len(values) == 1:
            if values[0] in self.strings:
                setattr(namespace, self.dest, values[0])
                return None
            elif isinstance(values[0], str):
                raise argparse.ArgumentTypeError(
                    self,
                    f"allowed strings are {self.strings}, but received {values[0]}",
                )
            else:
                raise argparse.ArgumentTypeError(
                    self, f"required two values, but received one value ({values})"
                )
        elif len(values) == 2:
            for i in range(2):
                v = convert(self, values[i])
                if v is not None:
                    if not self.min <= v <= self.max:
                        raise argparse.ArgumentTypeError(
                            self,
                            f"expected values between {self.min} and {self.max}, but received {v}",
                        )
                checked_values.append(v)
            if not any(v is None for v in checked_values):
                checked_values.sort()
            else:
                if checked_values[0] is None:
                    checked_values[0] = self.min
                if checked_values[1] is None:
                    checked_values[1] = self.max
            setattr(namespace, self.dest, checked_values)
            return None
        else:
            raise argparse.ArgumentTypeError(
                self,
                f"too much values: expected at most two but received {len(values)}",
            )


class Store_boolean(argparse.Action):

    def __init__(self, *args, **kwargs):
        kwargs.update({"type": str, "metavar": "BOOL"})
        super(Store_boolean, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        if value.lower() in ("0", "n", "no", "false"):
            value = False
        elif value.lower() in ("1", "y", "yes", "true"):
            value = True
        else:
            raise argparse.ArgumentTypeError("Boolean value expected.")
        setattr(namespace, self.dest, value)


class Store_prefix(argparse.Action):

    def __init__(self, *args, **kwargs):
        kwargs.update({"type": str, "metavar": "LITERAL"})
        super(Store_prefix, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        if value:
            value = value if value[-1] in ["-", "_"] else value + "_"
        setattr(namespace, self.dest, value)


class Store_dict(argparse.Action):

    def __init__(
        self,
        type_key: type = str,
        type_value: type = str,
        sep: str = ":",
        *args,
        **kwargs,
    ):

        if isinstance(type_key, type):
            metavar_key = "LITERAL" if type_key is str else type_key.__name__.upper()
            self.type_key = type_key
        else:
            raise TypeError(
                f"unsupported parameter type for 'type_key': expected '{type}' but received '{type(type_key)}'"
            )

        if isinstance(type_value, type):
            metavar_value = (
                "LITERAL" if type_value is str else type_value.__name__.upper()
            )
            self.type_value = type_value
        else:
            raise TypeError(
                f"unsupported parameter type for 'type_key': expected '{type}' but received '{type(type_value)}'"
            )

        if isinstance(sep, str):
            self.sep = sep
        else:
            raise TypeError(
                f"unsupported parameter type for 'sep': expected '{str}' but received '{type(sep)}'"
            )

        if "nargs" not in kwargs:
            kwargs["nargs"] = "+"

        kwargs["metavar"] = f"{metavar_key}{sep}{metavar_value}"
        super(Store_dict, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        values = cast(Sequence[str], values)
        setattr(namespace, self.dest, dict())
        for element in values:
            k, v = element.split(self.sep)
            k = self.type_key(k)
            v = self.type_value(v)
            getattr(namespace, self.dest)[k] = v


class Store_organism(argparse.Action):

    def __init__(self, *args, **kwargs):
        default = kwargs["default"] if "default" in kwargs else None
        choices = (
            kwargs["choices"]
            if "choices" in kwargs
            else ["mouse", "human", "escherichia-coli"]
        )
        kwargs.update(
            {
                "type": str,
                "choices": choices,
                "metavar": "ORGANISM",
                "default": default,
                "help": (
                    kwargs["help"]
                    if "help" in kwargs
                    else f"common name of the organism of interest (default: {default})"
                ),
            }
        )
        super(Store_organism, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):

        if value == "escherichia-coli":
            value = "escherichia coli"
        setattr(namespace, self.dest, value)


class Required_length(argparse.Action):

    def __init__(
        self, min: int = 0, max: Union[int, float] = math.inf, *args, **kwargs
    ):
        self.min = min
        self.max = max
        kwargs.update({"nargs": "*"})
        super(Required_length, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        values = cast(Sequence[object], values)
        if not self.min <= len(values) <= self.max:
            raise argparse.ArgumentTypeError(
                self,
                f"argument {self.dest} requires between {self.min} and {self.max} arguments",
            )
        setattr(namespace, self.dest, values)


class Store_axis(argparse.Action):

    def __init__(self, *args, **kwargs):
        kwargs.update(
            {
                "type": str,
                "metavar": "[0 | 1 | obs | var]",
                "choices": ["0", "1", "obs", "var"],
            }
        )
        super(Store_axis, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        if value == "0":
            value = "obs"
        elif value == "1":
            value = "var"
        setattr(namespace, self.dest, value)


class Store_type(argparse.Action):

    def __init__(self, *args, **kwargs):

        kwargs.update(
            {
                "type": str,
                "choices": (
                    ["str", "int", "float", "complex", "bool", "category"]
                    if "choices" not in kwargs
                    else kwargs["choices"]
                ),
                "metavar": "TYPE",
            }
        )
        super(Store_type, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):

        if value == "str":
            value = str
        elif value == "int":
            value = int
        elif value == "float":
            value = float
        elif value == "complex":
            value = complex
        elif value == "bool":
            value = bool
        elif value == "category":
            pass
        else:
            raise argparse.ArgumentError(self, f"invalid value: '{value}'")

        setattr(namespace, self.dest, value)


class Store_metric(argparse.Action):

    def __init__(self, *args, **kwargs):

        if "choices" in kwargs:
            choices = kwargs["choices"]
        else:
            choices = [
                "cityblock",
                "cosine",
                "euclidean",
                "l1",
                "l2",
                "manhattan",
                "braycurtis",
                "canberra",
                "chebyshev",
                "correlation",
                "dice",
                "hamming",
                "jaccard",
                "kulsinski",
                "mahalanobis",
                "minkowski",
                "rogerstanimoto",
                "russellrao",
                "seuclidean",
                "sokalmichener",
                "sokalsneath",
                "sqeuclidean",
                "yule",
            ]
        kwargs.update(
            {
                "type": str,
                "choices": choices,
                "default": kwargs["default"] if "default" in kwargs else "euclidean",
                "metavar": "METRIC",
                "help": kwargs["help"] if "help" in kwargs else "distance metric",
            }
        )
        super(Store_metric, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        setattr(namespace, self.dest, value)


class Bonesis_mode(argparse.Action):

    def check_bonesis_mode(self, v):
        if v in ["soft", "relaxed", "hard"]:
            return None
        else:
            raise argparse.ArgumentError(self, f"invalid parameter value: {v}")

    def __init__(self, *args, **kwargs):
        if "required" in kwargs:
            required = kwargs["required"]
        else:
            required = False
        if "default" in kwargs:
            self.check_bonesis_mode(kwargs["default"])
            default = kwargs["default"]
        else:
            default = "hard"
        help = (
            "constraints retained for BoNesis\n"
            "soft: exclude non-reachability and universal constraints\n"
            "relaxed: exclude universal constraints\n"
            "hard: all constraints\n"
            f"default: {default if default else 'None'}"
        )
        kwargs.update(
            {
                "type": str,
                "required": required,
                "default": default,
                "metavar": "[soft | relaxed | hard]",
                "help": kwargs["help"] if "help" in kwargs else help,
            }
        )
        super(Bonesis_mode, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        self.check_bonesis_mode(value)
        setattr(namespace, self.dest, value)


class Clingo_opt_mode(argparse.Action):

    VALID_MODES = ("opt", "optN", "ignore")
    ENUM_PREFIX = "enum,"

    def __init__(self, *args, **kwargs):
        default = kwargs.get("default", None)
        if default is not None:
            self._check_opt_mode(default)
        kwargs.update(
            {
                "type": str,
                "default": default,
                "metavar": "[opt | optN | ignore | enum,<bound>[,<bound>...]]",
                "help": (
                    kwargs["help"]
                    if "help" in kwargs
                    else f"clingo optimization mode: opt, optN, ignore, or enum,<bound>[,<bound>...] (default: {default})"
                ),
            }
        )
        super(Clingo_opt_mode, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        self._check_opt_mode(value)
        setattr(namespace, self.dest, value)

    def _check_opt_mode(self, value):
        if value in self.VALID_MODES:
            return None
        if value.startswith(self.ENUM_PREFIX):
            bounds = value.removeprefix(self.ENUM_PREFIX).split(",")
            if bounds and all(self._is_int(bound) for bound in bounds):
                return None
            raise argparse.ArgumentError(
                self,
                f"invalid parameter value: expected enum,<bound>[,<bound>...] but received {value}",
            )
        raise argparse.ArgumentError(
            self,
            f"invalid parameter value: expected opt, optN, ignore, or enum,<bound>[,<bound>...] but received {value}",
        )

    def _is_int(self, value):
        try:
            int(value)
        except ValueError:
            return False
        return True


class Clingo_opt_strategy(argparse.Action):

    def check_opt_strategy(self, v):
        if v.startswith("bb") or v.startswith("usc"):
            return None
        else:
            raise argparse.ArgumentError(self, f"invalid parameter value: {v}")

    def __init__(self, *args, **kwargs):
        if "default" in kwargs:
            self.check_opt_strategy(kwargs["default"])
            default = kwargs["default"]
        else:
            default = None
        kwargs.update(
            {
                "type": str,
                "default": default,
                "metavar": "[bb[,<method>] | usc[,<method>]]",
                "help": (
                    kwargs["help"]
                    if "help" in kwargs
                    else f"clingo optimization strategy (default: {default})"
                ),
            }
        )
        super(Clingo_opt_strategy, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        self.check_opt_strategy(value)
        setattr(namespace, self.dest, value)


class Clingo_parallel_mode(argparse.Action):

    VALID_MODES = ("compete", "split")
    MIN_THREADS = 1
    MAX_THREADS = 64

    def __init__(self, *args, **kwargs):
        default = kwargs.get("default", "1")
        if default is not None:
            default = self._normalize_parallel_mode(default)
        kwargs.update(
            {
                "type": str,
                "default": default,
                "metavar": "INT",
                "help": (
                    kwargs["help"]
                    if "help" in kwargs
                    else f"number of Clingo jobs (default: {default})"
                ),
            }
        )
        super(Clingo_parallel_mode, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        setattr(namespace, self.dest, self._normalize_parallel_mode(value))

    def _normalize_parallel_mode(self, value):
        value = str(value).strip()
        parts = value.split(",")

        if len(parts) == 1:
            return str(self._check_threads(parts[0]))

        if len(parts) == 2:
            threads = self._check_threads(parts[0])
            mode = parts[1].strip().lower()
            if mode in self.VALID_MODES:
                return f"{threads},{mode}"
            raise argparse.ArgumentError(
                self,
                f"invalid parameter value: expected split or compete but received {parts[1]}",
            )

        raise argparse.ArgumentError(
            self,
            f"invalid parameter value: expected INT or INT,<mode> but received {value}",
        )

    def _check_threads(self, value):
        value = value.strip()
        try:
            threads = int(value)
        except ValueError:
            raise argparse.ArgumentError(
                self,
                f"invalid parameter value: expected an integer but received {value}",
            )

        if self.MIN_THREADS <= threads <= self.MAX_THREADS:
            return threads

        raise argparse.ArgumentError(
            self,
            (
                f"invalid parameter value: expected an integer between "
                f"{self.MIN_THREADS} and {self.MAX_THREADS} but received {threads}"
            ),
        )


class Bonesis_domain(argparse.Action):

    VALID_DOMAINS = {"collectri", "dorothea"}

    def check_domain(self, value):
        if value in self.VALID_DOMAINS:
            return value

        path = Path(value)
        if path.is_file():
            return path

        raise argparse.ArgumentError(
            self,
            (
                f"invalid parameter value: {value} "
                f"(expected {', '.join(sorted(self.VALID_DOMAINS))} or an existing file path)"
            ),
        )

    def __init__(self, *args, **kwargs):
        default = kwargs.get("default", "collectri")
        required = kwargs.get("required", False)

        self.check_domain(default)

        help = (
            "prior interaction domain defining the Boolean network search space; "
            "accepted values are 'collectri', 'dorothea', or a custom file path "
            f"(default: {default})"
        )

        kwargs.update(
            {
                "type": str,
                "required": required,
                "default": default,
                "metavar": "[collectri | dorothea | FILE]",
                "help": kwargs["help"] if "help" in kwargs else help,
            }
        )

        super(Bonesis_domain, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        value = self.check_domain(value)
        setattr(namespace, self.dest, value)
