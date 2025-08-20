#!/usr/bin/env python3
#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root
# of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
#

import argparse
import functools
import json
import os
import pathlib
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

import sys
sys.path.append(str(Path(__file__).parent.parent.parent / 'Scripts'))
from builders.vcpkgbuilder import VcpkgBuilder
import builders.monkeypatch_tempdir_cleanup

class BlastBuilder(object):
    def __init__(self, workingDir: pathlib.Path, targetPlatform: str):
        self._workingDir = workingDir
        self._platform = targetPlatform
        self._env = dict(os.environ)
        self._env.update(
            PM_PACKAGES_ROOT=str(workingDir / 'packman-repo'),
        )

        self.check_call = functools.partial(subprocess.check_call,
            cwd=self.workingDir,
            env=self.env
        )

    @property
    def workingDir(self):
        return self._workingDir

    @property
    def platform(self):
        return self._platform

    @property
    def env(self):
        return self._env

    def clone(self, lockToCommit: str):
        if not (self.workingDir / '.git').exists():
            self.check_call(
                ['git', 'init',],
            )
            self.check_call(
                ['git', 'remote', 'add', 'origin', 'https://github.com/NVIDIA-Omniverse/PhysX.git',],
            )

        self.check_call(
            ['git', 'fetch', 'origin', '--depth=1', lockToCommit,],
        )
        self.check_call(
            ['git', 'checkout', lockToCommit,],
        )

    def build(self):
        blast_dir = self.workingDir / 'blast'
        for config in ('release', 'debug'):
            if self.platform == 'windows':
                self.check_call(
                    ['cmd.exe', '/C', 'build.bat', '--config', config],
                    cwd=blast_dir
                )
            else:
                self.check_call(
                    ['sh', 'build.sh', '--config', config],
                    cwd=blast_dir
                )

    def copyBuildOutputTo(self, packageDir: pathlib.Path):
        if packageDir.exists():
            shutil.rmtree(packageDir)

        platform_params = {
            'windows': 'windows-x86_64',
            'linux': 'linux-x86_64'
        }
        for config in ('release', 'debug'):
            build_output_dir = self.workingDir / 'blast' / '_build' / platform_params[self.platform] / config / 'blast-sdk'
            if config == 'release':
                shutil.copytree(
                    src=build_output_dir / 'PACKAGE-LICENSES',
                    dst=packageDir,
                )
                shutil.move(
                    src=build_output_dir / 'include',
                    dst=packageDir / 'include',
                )
            shutil.move(
                src=build_output_dir / 'bin',
                dst=packageDir / config / 'bin'
            )

    def writePackageInfoFile(self, packageDir: pathlib.Path, settings: dict):
        with (packageDir / 'PackageInfo.json').open('w') as fh:
            json.dump(settings, fh, indent=4)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--platform-name',
        dest='platformName',
        choices=['windows', 'linux'],
        default=VcpkgBuilder.defaultPackagePlatformName(),
    )
    args = parser.parse_args()

    packageSystemDir = Path(__file__).resolve().parents[1]
    packageSourceDir = packageSystemDir / 'Blast'
    packageRoot = packageSystemDir / f'Blast-{args.platformName}'

    cmakeFindFile = packageSourceDir / f'FindBlast_{args.platformName}.cmake'
    if not cmakeFindFile.exists():
        cmakeFindFile = packageSourceDir / 'FindBlast.cmake'

    with TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)
        builder = BlastBuilder(workingDir=tempdir, targetPlatform=args.platformName)
        builder.clone('5ca9f472105a90d70d957c243cb0ef36fe251a9f')
        builder.build()
        builder.copyBuildOutputTo(packageRoot/'Blast')

        builder.writePackageInfoFile(
            packageRoot,
            settings={
                'PackageName': f'Blast-v5.0.6-rev1-{args.platformName}',
                'URL': 'https://github.com/NVIDIA-Omniverse/PhysX.git',
                'License': 'custom',
                'LicenseFile': 'Blast/license.txt',
            },
        )

        shutil.copy2(
            src=cmakeFindFile,
            dst=packageRoot / 'FindBlast.cmake'
        )

if __name__ == '__main__':
    main()
