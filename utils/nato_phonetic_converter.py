# utils/nato_phonetic_converter.py

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class ConversionResult:
    """
    Structured result returned by NATOPhoneticConverter.
    """

    original_text: str
    normalized_text: str
    converted_value: str
    language: str
    letters: list[str] = field(default_factory=list)
    digits: list[str] = field(default_factory=list)
    tokens: list[str] = field(default_factory=list)
    phonetic_words_found: list[str] = field(default_factory=list)
    ignored_tokens: list[str] = field(default_factory=list)
    contains_phonetic: bool = False

    def to_dict(self) -> dict[str, Any\]:
        return {
            "original_text": self.original_text,
            "normalized_text": self.normalized_text,
            "converted_value": self.converted_value,
            "language": self.language,
            "letters": self.letters,
            "digits": self.digits,
            "tokens": self.tokens,
            "phonetic_words_found": self.phonetic_words_found,
            "ignored_tokens": self.ignored_tokens,
            "contains_phonetic": self.contains_phonetic,
        }


class NATOPhoneticConverter:
    """
    Convert spoken NATO phonetic words and number words into an
    alphanumeric identifier.

    Supported languages:
        English: en, eng, english
        Spanish: es, spa, spanish, espanol
        French:  fr, fra, french, francais

    Examples:
        "Mike Alfa one two nine"       -> "MA129"
        "M as in Mike A as in Alfa"    -> "MA"
        "Mike Alfa uno dos nueve"      -> "MA129"
        "Mike Alfa un deux neuf"       -> "MA129"
        "Charlie Lima Mike one zero"   -> "CLM10"
    """

    NATO_ALPHABET: ClassVar[dict[str, str]] = {
        "alfa": "A",
        "alpha": "A",
        "bravo": "B",
        "charlie": "C",
        "delta": "D",
        "echo": "E",
        "foxtrot": "F",
        "golf": "G",
        "hotel": "H",
        "india": "I",
        "juliett": "J",
        "juliet": "J",
        "kilo": "K",
        "lima": "L",
        "mike": "M",
        "november": "N",
        "oscar": "O",
        "papa": "P",
        "quebec": "Q",
        "romeo": "R",
        "sierra": "S",
        "tango": "T",
        "uniform": "U",
        "victor": "V",
        "whiskey": "W",
        "whisky": "W",
        "xray": "X",
        "x-ray": "X",
        "yankee": "Y",
        "zulu": "Z",
    }

    NUMBER_WORDS: ClassVar[dict[str, dict[str, str]]] = {
        "en": {
            "zero": "0",
            "oh": "0",
            "o": "0",
            "one": "1",
            "won": "1",
            "two": "2",
            "to": "2",
            "too": "2",
            "three": "3",
            "tree": "3",
            "four": "4",
            "for": "4",
            "five": "5",
            "fife": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "ate": "8",
            "nine": "9",
            "niner": "9",
        },
        "es": {
            "cero": "0",
            "uno": "1",
            "una": "1",
            "un": "1",
            "dos": "2",
            "tres": "3",
            "cuatro": "4",
            "cinco": "5",
            "seis": "6",
            "siete": "7",
            "ocho": "8",
            "nueve": "9",
        },
        "fr": {
            "zero": "0",
            "zéro": "0",
            "un": "1",
            "une": "1",
            "deux": "2",
            "trois": "3",
            "quatre": "4",
            "cinq": "5",
            "six": "6",
            "sept": "7",
            "huit": "8",
            "neuf": "9",
        },
    }

    LANGUAGE_ALIASES: ClassVar[dict[str, str]] = {
        "en": "en",
        "eng": "en",
        "english": "en",
        "es": "es",
        "spa": "es",
        "spanish": "es",
        "espanol": "es",
        "español": "es",
        "fr": "fr",
        "fra": "fr",
        "fre": "fr",
        "french": "fr",
        "francais": "fr",
        "français": "fr",
    }

    # Words that do not contribute to the identifier.
    FILLER_WORDS: ClassVar[dict[str, set[str]]] = {
        "en": {
            "as",
            "in",
            "for",
            "letter",
            "the",
            "is",
            "like",
            "and",
            "dash",
            "hyphen",
            "space",
        },
        "es": {
            "como",
            "en",
            "por",
            "para",
            "letra",
            "la",
            "el",
            "es",
            "y",
            "guion",
            "espacio",
        },
        "fr": {
            "comme",
            "dans",
            "pour",
            "lettre",
            "la",
            "le",
            "est",
            "et",
            "tiret",
            "espace",
        },
    }

    # Common ASR variations for NATO words.
    NATO_ALIASES: ClassVar[dict[str, str]] = {
        "alfah": "alfa",
        "alfa": "alfa",
        "alpha": "alfa",
        "bravoh": "bravo",
        "charly": "charlie",
        "charley": "charlie",
        "dellta": "delta",
        "ekko": "echo",
        "fox trot": "foxtrot",
        "fox-trot": "foxtrot",
        "foxtrot": "foxtrot",
        "hotell": "hotel",
        "julliett": "juliett",
        "juliette": "juliett",
        "kilo": "kilo",
        "keylo": "kilo",
        "lee-ma": "lima",
        "leema": "lima",
        "novembre": "november",
        "noviembre": "november",
        "oskar": "oscar",
        "pappa": "papa",
        "quebec": "quebec",
        "québec": "quebec",
        "romeo": "romeo",
        "roméo": "romeo",
        "uniforme": "uniform",
        "whisky": "whiskey",
        "x ray": "xray",
        "x-ray": "xray",
        "xray": "xray",
    }

    def __init__(
        self,
        default_language: str = "en",
        preserve_unknown_alphanumeric: bool = True,
    ) -> None:
        self.default_language = self.normalize_language(
            default_language
        )

        self.preserve_unknown_alphanumeric = (
            preserve_unknown_alphanumeric
        )

        self._all_number_words = self._build_all_number_words()
        self._all_fillers = set().union(
            *self.FILLER_WORDS.values()
        )

    @classmethod
    def normalize_language(
        cls,
        language: str | None,
    ) -> str:
        if not language:
            return "en"

        normalized = cls._normalize_word(language)

        return cls.LANGUAGE_ALIASES.get(
            normalized,
            "en",
        )

    @staticmethod
    def _normalize_word(value: str) -> str:
        """
        Lowercase text and remove accents.

        Examples:
            "ZÉRO"     -> "zero"
            "Español"  -> "espanol"
            "Québec"   -> "quebec"
        """

        normalized = unicodedata.normalize(
            "NFKD",
            str(value),
        )

        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )

        return normalized.casefold().strip()

    @classmethod
    def _build_all_number_words(cls) -> dict[str, str\]:
        combined: dict[str, str] = {}

        for language_words in cls.NUMBER_WORDS.values():
            for word, digit in language_words.items():
                combined[cls._normalize_word(word)] = digit

        return combined

    @classmethod
    def _prepare_text(cls, text: str) -> str:
        normalized = cls._normalize_word(text)

        # Normalize common multiword NATO expressions before tokenizing.
        replacements = {
            r"\bfox[\s-]+trot\b": "foxtrot",
            r"\bx[\s-]+ray\b": "xray",
            r"\bas\s+in\b": " ",
            r"\bas\s+for\b": " ",
            r"\bcomo\s+en\b": " ",
            r"\bcomme\s+dans\b": " ",
        }

        for pattern, replacement in replacements.items():
            normalized = re.sub(
                pattern,
                replacement,
                normalized,
                flags=re.IGNORECASE,
            )

        # Keep letters and numbers. Convert punctuation to spaces.
        normalized = re.sub(
            r"[^a-z0-9]+",
            " ",
            normalized,
        )

        return re.sub(
            r"\s+",
            " ",
            normalized,
        ).strip()

    def _get_number_words(
        self,
        language: str,
        accept_all_languages: bool,
    ) -> dict[str, str\]:
        if accept_all_languages:
            return self._all_number_words

        words = self.NUMBER_WORDS.get(
            language,
            self.NUMBER_WORDS["en"],
        )

        return {
            self._normalize_word(word): digit
            for word, digit in words.items()
        }

    def _get_filler_words(
        self,
        language: str,
        accept_all_languages: bool,
    ) -> set[str\]:
        if accept_all_languages:
            return self._all_fillers

        return self.FILLER_WORDS.get(
            language,
            self.FILLER_WORDS["en"],
        )

    def convert(
        self,
        text: str | None,
        language: str | None = None,
        *,
        accept_all_languages: bool = True,
        keep_spaces: bool = False,
    ) -> ConversionResult:
        """
        Convert spoken phonetic input into an identifier.

        accept_all_languages=True allows mixed input such as:
            "Mike Alfa uno two neuf"

        The output is:
            "MA129"
        """

        original_text = str(text or "")
        selected_language = self.normalize_language(
            language or self.default_language
        )

        normalized_text = self._prepare_text(
            original_text
        )

        if not normalized_text:
            return ConversionResult(
                original_text=original_text,
                normalized_text="",
                converted_value="",
                language=selected_language,
            )

        number_words = self._get_number_words(
            selected_language,
            accept_all_languages,
        )

        filler_words = self._get_filler_words(
            selected_language,
            accept_all_languages,
        )

        output: list[str] = []
        letters: list[str] = []
        digits: list[str] = []
        phonetic_words: list[str] = []
        ignored_tokens: list[str] = []

        tokens = normalized_text.split()

        index = 0

        while index < len(tokens):
            token = tokens[index]

            # Handle compact values already recognized by ASR:
            # CLM100001, MA1001, etc.
            if re.fullmatch(
                r"[a-z]+\d+|\d+[a-z]+|[a-z]+\d+[a-z0-9]*",
                token,
            ):
                compact_value = token.upper()

                output.append(compact_value)

                letters.extend(
                    character
                    for character in compact_value
                    if character.isalpha()
                )

                digits.extend(
                    character
                    for character in compact_value
                    if character.isdigit()
                )

                index += 1
                continue

            nato_alias = self.NATO_ALIASES.get(
                token,
                token,
            )

            nato_letter = self.NATO_ALPHABET.get(
                nato_alias
            )

            if nato_letter:
                output.append(nato_letter)
                letters.append(nato_letter)
                phonetic_words.append(token)
                index += 1
                continue

            digit = number_words.get(token)

            if digit is not None:
                output.append(digit)
                digits.append(digit)
                index += 1
                continue

            # Preserve literal digit groups, including leading zeroes.
            if token.isdigit():
                output.append(token)
                digits.extend(list(token))
                index += 1
                continue

            # Preserve a directly spoken single letter.
            if len(token) == 1 and token.isalpha():
                letter = token.upper()
                output.append(letter)
                letters.append(letter)
                index += 1
                continue

            if token in filler_words:
                ignored_tokens.append(token)
                index += 1
                continue

            if (
                self.preserve_unknown_alphanumeric
                and token.isalnum()
            ):
                value = token.upper()
                output.append(value)

                letters.extend(
                    character
                    for character in value
                    if character.isalpha()
                )

                digits.extend(
                    character
                    for character in value
                    if character.isdigit()
                )
            else:
                ignored_tokens.append(token)

            index += 1

        separator = " " if keep_spaces else ""

        return ConversionResult(
            original_text=original_text,
            normalized_text=normalized_text,
            converted_value=separator.join(output),
            language=selected_language,
            letters=letters,
            digits=digits,
            tokens=tokens,
            phonetic_words_found=phonetic_words,
            ignored_tokens=ignored_tokens,
            contains_phonetic=bool(phonetic_words),
        )

    def convert_value(
        self,
        text: str | None,
        language: str | None = None,
        *,
        accept_all_languages: bool = True,
    ) -> str:
        """
        enience method that returns only the converted identifier.
        """

        return self.convert(
            text=text,
            language=language,
            accept_all_languages=accept_all_languages,
        ).converted_value

    def convert_member_id(
        self,
        text: str | None,
        language: str | None = None,
        *,
        prepend_ma_when_phonetic: bool = False,
    ) -> str:
        """
        Convert spoken Member ID input.

        If prepend_ma_when_phonetic=True:
            "Mike one two nine" -> "MA129"

        Existing MA values are not duplicated:
            "Mike Alfa one two nine" -> "MA129"
        """

        result = self.convert(
            text=text,
            language=language,
            accept_all_languages=True,
        )

        value = result.converted_value

        if not value:
            return ""

        if (
            prepend_ma_when_phonetic
            and result.contains_phonetic
            and not value.startswith("MA")
        ):
            numeric_part = "".join(
                character
                for character in value
                if character.isdigit()
            )

            if numeric_part:
                return f"MA{numeric_part}"

        return value

    def to_nato(
        self,
        value: str | None,
        include_digits: bool = True,
    ) -> str:
        """
        Convert an identifier into NATO words for confirmation.

        Example:
            "MA1001" ->
            "Mike Alfa One Zero Zero One"
        """

        if value is None:
            return ""

        reverse_nato = {
            letter: word.title()
            for word, letter in self.NATO_ALPHABET.items()
            if word not in {"alpha", "juliet", "whisky", "x-ray"}
        }

        # Enforce official spellings.
        reverse_nato.update(
            {
                "A": "Alfa",
                "J": "Juliett",
                "W": "Whiskey",
                "X": "X-ray",
            }
        )

        reverse_digits = {
            "0": "Zero",
            "1": "One",
            "2": "Two",
            "3": "Three",
            "4": "Four",
            "5": "Five",
            "6": "Six",
            "7": "Seven",
            "8": "Eight",
            "9": "Nine",
        }

        spoken_parts: list[str] = []

        for character in str(value).upper():
            if character in reverse_nato:
                spoken_parts.append(
                    reverse_nato[character]
                )

            elif include_digits and character in reverse_digits:
                spoken_parts.append(
                    reverse_digits[character]
                )

        return " ".join(spoken_parts)