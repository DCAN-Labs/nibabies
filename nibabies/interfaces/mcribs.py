import os
import shutil
from pathlib import Path

from nipype.interfaces.base import (
    CommandLine,
    CommandLineInputSpec,
    Directory,
    File,
    TraitedSpec,
    traits,
)


class MCRIBReconAllInputSpec(CommandLineInputSpec):
    # Input structure massaging
    subjects_dir = Directory(
        exists=True,
        hash_files=False,
        desc='path to subjects directory',
        required=True,
    )
    subject_id = traits.Str(
        # required=True,
        argstr='%s',
        position=-1,
        desc='subject name',
    )
    t1w_file = File(
        exists=True,
        copyfile=True,
        desc='T1w to be used for deformable (must be registered to T2w image)',
    )
    t2w_file = File(
        exists=True,
        required=True,
        copyfile=True,
        desc='T2w (Isotropic + N4 corrected)',
    )
    segmentation_file = File(
        desc='Segmentation file (skips tissue segmentation)',
    )

    # MCRIBS options
    conform = traits.Bool(
        argstr='--conform',
        desc='Reorients to radiological, axial slice orientation. Resamples to isotropic voxels',
    )
    tissueseg = traits.Bool(
        argstr='--tissueseg',
        desc='Perform tissue type segmentation',
    )
    surfrecon = traits.Bool(
        True,
        usedefault=True,
        argstr='--surfrecon',
        desc='Reconstruct surfaces',
    )
    surfrecon_method = traits.Enum(
        'Deformable',
        argstr='--surfreconmethod %s',
        usedefault=True,
        desc='Surface reconstruction method',
    )
    join_thresh = traits.Float(
        1.0,
        argstr='--deformablejointhresh %f',
        usedefault=True,
        desc='Join threshold parameter for Deformable',
    )
    fast_collision = traits.Bool(
        True,
        argstr='--deformablefastcollision',
        usedefault=True,
        desc='Use Deformable fast collision test',
    )
    autorecon_after_surf = traits.Bool(
        True,
        argstr='--autoreconaftersurf',
        usedefault=True,
        desc='Do all steps after surface reconstruction',
    )
    segstats = traits.Bool(
        True,
        argstr='--segstats',
        usedefault=True,
        desc='Compute statistics on segmented volumes',
    )
    nthreads = traits.Int(
        argstr='-nthreads %d',
        desc='Number of threads for multithreading applications',
    )


class MCRIBReconAllOutputSpec(TraitedSpec):
    mcribs_dir = Directory(desc='MCRIBS output directory')


class MCRIBReconAll(CommandLine):
    _cmd = 'MCRIBReconAll'
    input_spec = MCRIBReconAllInputSpec
    output_spec = MCRIBReconAllOutputSpec

    def _setup_directory_structure(self, mcribs_dir: Path) -> None:
        '''
        Create the required structure for skipping steps.

        The directory tree
        ------------------

        <subject_id>/
        ├── RawT2
        │   └── <subject_id>.nii.gz
        ├── SurfReconDeformable
        │   └── <subject_id>
        │       └── temp
        │           └── t2w-image.nii.gz
        ├── TissueSeg
        │   ├── <subject_id>_all_labels.nii.gz
        │   └── <subject_id>_all_labels_manedit.nii.gz
        └── TissueSegDrawEM
            └── <subject_id>
                └── N4
                    └── <subject_id>.nii.gz
        '''
        sid = self.inputs.subject_id
        mkdir_kw = {'parents': True, 'exist_ok': True}
        root = mcribs_dir / sid
        root.mkdir(**mkdir_kw)

        # T2w operations
        t2w = root / 'RawT2' / f'{sid}.nii.gz'
        t2w.parent.mkdir(**mkdir_kw)
        if not t2w.exists():
            shutil.copy(self.inputs.t2w_file, str(t2w))

        if not self.inputs.conform:
            t2wiso = root / 'RawT2RadiologicalIsotropic' / f'{sid}.nii.gz'
            t2wiso.parent.mkdir(**mkdir_kw)
            if not t2wiso.exists():
                t2wiso.symlink_to(f'../../RawT2/{sid}.nii.gz')

            n4 = root / sid / 'N4' / f'{sid}.nii.gz'
            n4.parent.mkdir(**mkdir_kw)
            if not n4.exists():
                n4.symlink_to(f'../../../RawT2/{sid}.nii.gz')

        # Segmentation
        if self.inputs.segmentation_file:
            # TissueSeg directive disabled
            tisseg = root / 'TissueSeg' / f'{sid}_all_labels.nii.gz'
            tisseg.parent.mkdir(**mkdir_kw)
            if not tisseg.exists():
                shutil.copy(self.inputs.segmentation, str(tisseg))
            manedit = tisseg.parent / f'{sid}_all_labels_manedit.nii.gz'
            if not manedit.exists():
                manedit.symlink_to(tisseg.name)

            if self.inputs.surfrecon:
                surfrec = root / 'SurfReconDeformable' / sid / 'temp' / 't2w-image.nii.gz'
                surfrec.parent.mkdir(**mkdir_kw)
                if not surfrec.exists():
                    surfrec.symlink_to(f'../../../../RawT2/{sid}.nii.gz')

        # TODO: T1w -> <subject_id>/RawT1RadiologicalIsotropic/<subjectid>.nii.gz
        return

    def _run_interface(self, runtime):
        # if users wish to preserve their runs
        mcribs_dir = os.getenv('MCRIBS_SUBJECTS')
        if mcribs_dir is None or not Path(mcribs_dir).exists():
            mcribs_dir = runtime.cwd / 'mcribs'
        self._mcribs_dir = mcribs_dir
        self._setup_directory_structure(mcribs_dir)
        # runs in CWD
        os.chdir(mcribs_dir / self.inputs.subject_id)
        return super()._run_interface(runtime)

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['mcribs_dir'] = self._mcribs_dir

        # TODO: Copy freesurfer directory into FS subjects dir
        # fs_outputs = self._mcribs_dir / self.inputs.subject_id / 'freesurfer'
        # if fs_outputs.exists():
        #     pass
        return outputs
