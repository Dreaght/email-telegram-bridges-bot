import secrets

_CONSONANT_CLUSTERS = (
    "b",
    "br",
    "c",
    "ch",
    "cl",
    "cr",
    "d",
    "dr",
    "f",
    "fl",
    "fr",
    "g",
    "gl",
    "gr",
    "h",
    "j",
    "k",
    "l",
    "m",
    "n",
    "p",
    "pl",
    "pr",
    "qu",
    "r",
    "s",
    "sc",
    "sh",
    "sk",
    "sl",
    "sm",
    "sn",
    "sp",
    "st",
    "str",
    "t",
    "th",
    "tr",
    "v",
    "w",
    "y",
    "z",
)

_VOWELS = ("a", "e", "i", "o", "u", "ae", "ai", "ea", "eo", "ia", "io", "oa", "oi", "ou", "ue")
_ENDINGS = ("", "n", "r", "s", "t", "x", "th", "nd", "rk", "lm", "nt", "sh")


def _random_word() -> str:
    syllable_count = secrets.randbelow(3) + 2  # 2-4 syllables
    parts: list[str] = []

    for _ in range(syllable_count):
        parts.append(secrets.choice(_CONSONANT_CLUSTERS))
        parts.append(secrets.choice(_VOWELS))

    parts.append(secrets.choice(_ENDINGS))
    return "".join(parts).capitalize()


def random_subject() -> str:
    word_count = secrets.randbelow(5) + 1
    return " ".join(_random_word() for _ in range(word_count))
