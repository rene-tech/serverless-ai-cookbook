"""Bounded, read-only previews of explicit workspace artifacts."""
import base64
import io
import math

import numpy as np
from PIL import Image
from scientific_study import path_in_workspace, workspace


def source_file(value):
    path = path_in_workspace(value)
    if not path.is_file() or path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError('Preview requires an existing workspace file up to 512 MiB. Download larger originals.')
    return path


def png(array):
    if array.shape[0] > 2048 or array.shape[1] > 2048:
        raise ValueError('Preview images are limited to 2048 pixels per axis.')
    output = io.BytesIO()
    Image.fromarray(array).save(output, format='PNG')
    if output.tell() > 4 * 1024 * 1024:
        raise ValueError('This frame exceeds the 4 MiB preview limit. Download the original.')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


def index(value, size):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < size:
        raise ValueError(f'Choose an index between 0 and {size - 1}.')
    return value


def volume(path):
    import nibabel as nib
    try:
        image = nib.load(path)
    except nib.filebasedimages.ImageFileError as error:
        raise ValueError('Choose a readable .nii or .nii.gz original for the CT/mask preview.') from error
    if len(image.shape) != 3 or any(n < 1 or n > 2048 for n in image.shape) or math.prod(image.shape) > 32 * 1024 * 1024:
        raise ValueError('Preview supports 3D volumes up to 32 million voxels and 2048 voxels per axis.')
    if not np.isfinite(image.affine).all() or abs(np.linalg.det(image.affine[:3, :3])) < 1e-12:
        raise ValueError('Image geometry is invalid; no anatomical orientation can be shown.')
    return image


def ct(body):
    import nibabel as nib
    image = volume(source_file(body.get('path')))
    axis = index(body.get('axis', 2), 3)
    selected = index(body.get('index', image.shape[axis] // 2), image.shape[axis])
    window, level, opacity = (float(body.get(name, default)) for name, default in [('window', 400), ('level', 40), ('opacity', 0.4)])
    if not all(math.isfinite(v) for v in [window, level, opacity]) or window <= 0 or not 0 <= opacity <= 1:
        raise ValueError('Window must be positive; level finite; mask opacity between 0 and 1.')
    selection = [slice(None)] * 3
    selection[axis] = selected
    values = np.asanyarray(image.dataobj[tuple(selection)]).T[::-1]
    if not np.isfinite(values).all():
        raise ValueError('The selected CT slice contains non-finite values.')
    gray = (np.clip((values.astype(float) - level) / window + 0.5, 0, 1) * 255).astype(np.uint8)
    rgb = np.repeat(gray[..., None], 3, axis=-1)
    if body.get('mask'):
        mask = volume(source_file(body['mask']))
        if mask.shape != image.shape or not np.allclose(mask.affine, image.affine, rtol=0, atol=1e-5) or mask.header.get_xyzt_units()[0] != image.header.get_xyzt_units()[0]:
            raise ValueError('CT and mask geometry or units differ. Overlay refused; inspect/download originals separately.')
        labels = np.asanyarray(mask.dataobj[tuple(selection)]).T[::-1]
        if not np.isin(labels, [0, 1]).all():
            raise ValueError('This spleen overlay expects labels 0 and 1.')
        rgb[labels == 1] = ((1 - opacity) * rgb[labels == 1] + opacity * np.array([255, 80, 40])).astype(np.uint8)
    codes = nib.aff2axcodes(image.affine)
    remaining = [i for i in range(3) if i != axis]
    return {'kind': 'ct', 'image': png(rgb), 'shape': list(image.shape), 'index': selected,
            'axis_codes': list(codes), 'right': codes[remaining[0]], 'up': codes[remaining[1]],
            'units': image.header.get_xyzt_units()[0], 'spacing': list(map(float, image.header.get_zooms())),
            'notice': 'Original voxel plane; no resampling. Orientation follows the file affine. Window assumes CT values in HU. Research use only.'}


def hdf_object(root, path):
    import h5py
    obj = root
    for part in path.split('/'):
        if not part or part in {'.', '..'} or not isinstance(obj, h5py.Group) or not isinstance(obj.get(part, getlink=True), h5py.HardLink):
            raise ValueError('Preview requires ordinary in-file HDF5 objects, without soft/external links.')
        obj = obj[part]
    if isinstance(obj, h5py.Dataset) and (obj.is_virtual or obj.id.get_create_plist().get_external_count()):
        raise ValueError('External or virtual HDF5 datasets are not supported by this preview.')
    if isinstance(obj, h5py.Dataset) and obj.chunks and math.prod(obj.chunks) * obj.dtype.itemsize > 32 * 1024 * 1024:
        raise ValueError('HDF5 chunk exceeds the 32 MiB preview decode limit.')
    return obj


def episode(body):
    import h5py
    with h5py.File(source_file(body.get('path')), 'r') as recording:
        data = hdf_object(recording, 'data')
        if len(data) > 1000:
            raise ValueError('Preview supports up to 1000 episodes. Download this recording.')
        episodes = sorted(name for name in data if name.startswith('demo_'))
        if not episodes:
            raise ValueError('No recorded demo_ episodes are present in this HDF5 file.')
        name = body.get('episode') or episodes[0]
        if name not in episodes:
            raise ValueError('Select one of the recorded episode names.')
        demo = hdf_object(recording, 'data/' + name)
        obs = hdf_object(demo, 'obs')
        if len(obs) > 100:
            raise ValueError('Preview supports up to 100 recorded sensors per episode.')
        cameras = []
        for key in obs:
            item = hdf_object(obs, key)
            if isinstance(item, h5py.Dataset) and item.ndim == 4 and item.shape[-1] in (3, 4) and item.dtype == np.uint8:
                cameras.append(key)
        steps = int(demo.attrs.get('num_samples', 0))
        sample = index(body.get('index', 0), steps)
        camera = body.get('camera') or (cameras[0] if cameras else None)
        result = {'kind': 'episode', 'episodes': episodes, 'episode': name, 'cameras': cameras,
                  'camera': camera, 'samples': steps, 'index': sample,
                  'task_success': bool(demo.attrs['success']) if 'success' in demo.attrs else None,
                  'notice': 'Recorded samples only. No portable scene geometry was supplied; this is not a 3D simulation or a physics validation.'}
        if camera:
            if camera not in cameras:
                raise ValueError('Choose a recorded RGB camera from this episode.')
            frames = hdf_object(obs, camera)
            if frames.shape[0] != steps or max(frames.shape[1:3]) > 2048:
                raise ValueError('Camera samples do not align with the episode or exceed the preview size limit.')
            result['image'] = png(frames[sample])
        for key in ['actions', 'obs/joint_pos']:
            array = hdf_object(demo, key)
            if not isinstance(array, h5py.Dataset) or array.ndim < 2 or not np.issubdtype(array.dtype, np.number) or array.shape[0] != steps or math.prod(array.shape[1:]) > 256:
                raise ValueError('State/action preview requires aligned samples with at most 256 values each.')
            values = np.asarray(array[sample], dtype=float).ravel()
            result[key] = [float(v) if np.isfinite(v) else None for v in values]
        return result


def preview(model, body):
    if model == 'monai-spleen-ct':
        return ct(body)
    if model == 'isaac-healthcare':
        return episode(body)
    path = source_file(body.get('path'))
    if path.suffix.lower() != '.mp4' or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Video preview accepts an explicitly selected annotated MP4 up to 32 MiB. Download larger or other artifacts.')
    return {'kind': 'video', 'path': str(path.relative_to(workspace())),
            'size_bytes': path.stat().st_size,
            'notice': 'Recorded annotated pixels only. Playback time is not a source-frame index. Missing annotation is a valid output; raw masks are retained for analysis.'}
