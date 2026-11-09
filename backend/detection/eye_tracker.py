from math import hypot
from typing import Optional, Sequence


LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def euclidean(p1, p2):
    return hypot(p1[0] - p2[0], p1[1] - p2[1])


def eye_aspect_ratio(landmarks, eye_indices, width, height) -> Optional[float]:
    points = [
        (int(landmarks[index].x * width), int(landmarks[index].y * height))
        for index in eye_indices
    ]
    p1, p2, p3, p4, p5, p6 = points
    horizontal = euclidean(p1, p4)
    if horizontal == 0:
        return None

    vertical_1 = euclidean(p2, p6)
    vertical_2 = euclidean(p3, p5)
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def calculate_eye_ears(landmarks, width, height):
    required_index = max(LEFT_EYE + RIGHT_EYE)
    if len(landmarks) <= required_index:
        return None, None
    return (
        eye_aspect_ratio(landmarks, LEFT_EYE, width, height),
        eye_aspect_ratio(landmarks, RIGHT_EYE, width, height),
    )


def eye_status_from_ear(ear_mean: Optional[float], threshold: float) -> str:
    if ear_mean is None:
        return "TRACKING LOST"
    return "CLOSED" if ear_mean < threshold else "OPEN"
