"""Explicit first MONAI bundle contract; adding a bundle requires its own evidence."""

from copy import deepcopy

MODEL_ID = "monai-spleen-ct"
REPOSITORY = "Project-MONAI/model-zoo"
SOURCE = "feb2e8c318e1964de5d3e1c1000474571e03ad50"
BUNDLE = "MONAI/spleen_ct_segmentation"
BUNDLE_VERSION = "0.6.1"
BUNDLE_REVISION = "8c4da75225ff7cb30292729dd704cceccae5413c"
WEIGHTS_SHA256 = "502c312893994ec071a85c4f2e7d83a43f7789969faa73dae62f1291177f50fe"
PARAMETER_SCHEMA = "scientific-ai/monai-spleen-ct/v1"
INPUT_NAME, INPUT_SEMANTIC = "image", "ct-nifti-volume/v1"
MAX_BYTES = 128 * 1024**3  # Existing scientific artifact transport ceiling.
OPERATIONS = ["segment"]
PROPERTIES = {
    "precision": {
        "enum": ["float32", "float16", "bfloat16"], "default": "float32",
        "description": "Model arithmetic; output is always an integer segmentation in input geometry.",
    },
    "sw_batch_size": {
        "type": "integer", "minimum": 1, "default": 4,
        "description": "96-cubed patches per forward pass; lower this if the requested workload exhausts memory.",
    },
    "overlap": {
        "type": "number", "minimum": 0, "exclusiveMaximum": 1, "default": 0.5,
        "description": "Sliding window overlap; changing it changes the inference configuration.",
    },
    "spatial_units": {
        "enum": ["header", "mm", "meter", "micron"], "default": "header",
        "description": "Use NIfTI spatial units, or explicitly supply missing/incorrect units. "
        "Coordinates are converted to millimeters for the bundle and restored for the output.",
    },
}


def parameter_schema():
    return {"type": "object", "additionalProperties": False, "properties": deepcopy(PROPERTIES)}


def parameters(value, operation="segment"):
    from jsonschema import Draft202012Validator

    if operation not in OPERATIONS:
        raise ValueError("MONAI spleen CT supports operation 'segment'; choose its published workflow")
    errors = list(Draft202012Validator(parameter_schema()).iter_errors(value))
    if errors:
        field = "/".join(map(str, errors[0].path)) or "parameters"
        raise ValueError(f"Invalid MONAI {field}; follow the published parameter types and choices")
    import math
    if any(isinstance(v, float) and not math.isfinite(v) for v in value.values()):
        raise ValueError("MONAI parameters must contain finite values")
    result = {key: deepcopy(item["default"]) for key, item in PROPERTIES.items()}
    result.update(value)
    # JSON Schema integer includes integral JSON numbers such as 3.0.
    result["sw_batch_size"] = int(result["sw_batch_size"])
    return result
