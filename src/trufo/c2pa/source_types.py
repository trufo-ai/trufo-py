# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Writable C2PA digital source types supported by Trufo."""

from enum import Enum

_IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"


class DigitalSourceType(str, Enum):
    """Active IPTC Digital Source Type values accepted for claimed actions."""

    DIGITAL_CAPTURE = f"{_IPTC}digitalCapture"
    COMPUTATIONAL_CAPTURE = f"{_IPTC}computationalCapture"
    COMPOSITE_CAPTURE = f"{_IPTC}compositeCapture"
    SCREEN_CAPTURE = f"{_IPTC}screenCapture"
    NEGATIVE_FILM = f"{_IPTC}negativeFilm"
    POSITIVE_FILM = f"{_IPTC}positiveFilm"
    PRINT = f"{_IPTC}print"
    DIGITAL_CREATION = f"{_IPTC}digitalCreation"
    ALGORITHMIC_MEDIA = f"{_IPTC}algorithmicMedia"
    DATA_DRIVEN_MEDIA = f"{_IPTC}dataDrivenMedia"
    HUMAN_EDITS = f"{_IPTC}humanEdits"
    ALGORITHMICALLY_ENHANCED = f"{_IPTC}algorithmicallyEnhanced"
    COMPOSITE = f"{_IPTC}composite"
    COMPOSITE_SYNTHETIC = f"{_IPTC}compositeSynthetic"
    TRAINED_ALGORITHMIC_MEDIA = f"{_IPTC}trainedAlgorithmicMedia"
    VIRTUAL_RECORDING = f"{_IPTC}virtualRecording"
    COMPOSITE_WITH_TRAINED_ALGORITHMIC_MEDIA = f"{_IPTC}compositeWithTrainedAlgorithmicMedia"
