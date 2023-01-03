import io
import plistlib
import shutil
import stat
import subprocess
import zipfile
from os import chdir
from pathlib import Path

from hammock import Hammock as hammock


class Builder:
    def __init__(self):
        self.lilu = {}
        self.clang32 = None
        self.edk2 = None
        self.script_dir = Path(__file__).parent.absolute()

        self.working_dir = self.script_dir / Path("Temp")
        if self.working_dir.exists():
            shutil.rmtree(self.working_dir)
        self.working_dir.mkdir()

        self.build_dir = self.script_dir / Path("Builds")
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir()

    @staticmethod
    def _expand_globs(p: str):
        if "*" in p:
            path = Path(p)
            parts = path.parts[1:] if path.is_absolute() else path.parts
            return list(Path(path.root).glob(str(Path("").joinpath(*parts))))
        else:
            return [Path(p)]

    def _bootstrap_clang32(self, target_dir: Path):
        chdir(self.working_dir)
        clang_dir = self.working_dir / Path("clang32")

        if not self.clang32:
            print("Bootstrapping prerequisite: clang32...")
            if clang_dir.exists():
                shutil.rmtree(clang_dir)
            clang_dir.mkdir()
            chdir(clang_dir)
            print("\tDownloading clang32 binary...")
            zipfile.ZipFile(io.BytesIO(hammock("https://github.com/acidanthera/ocbuild/releases/download/llvm-kext32-latest/clang-12.zip").GET().content)).extractall()
            (clang_dir / Path("clang-12")).chmod((clang_dir / Path("clang-12")).stat().st_mode | stat.S_IEXEC)

            print("\tDownloading clang32 scripts...")
            for tool in ["fix-macho32", "libtool32"]:
                tool_path = Path(tool)
                tool_path.write_bytes(hammock(f"https://raw.githubusercontent.com/acidanthera/ocbuild/master/scripts/{tool}").GET().content)
                tool_path.chmod(tool_path.stat().st_mode | stat.S_IEXEC)
            self.clang32 = clang_dir.resolve()
        (target_dir / Path("clang32")).symlink_to(self.clang32)

    def _bootstrap_edk2(self):
        chdir(self.working_dir)
        if not self.edk2:
            print("Bootstrapping prerequisite: EDK II...")
            if Path("edk2").exists():
                shutil.rmtree(Path("edk2"))
            print("\tCloning the repo...")
            result = subprocess.run("git clone https://github.com/acidanthera/audk edk2 --branch master --depth 1".split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tClone failed!")
                print(result.stdout.decode())
                return False
            self.edk2 = True

    def _build_lilu(self):
        chdir(self.working_dir)
        if not self.lilu:
            print("Building prerequiste: Lilu...")
            if Path("Lilu").exists():
                shutil.rmtree(Path("Lilu"))
            print("\tCloning the repo...")
            result = subprocess.run("git clone https://github.com/acidanthera/Lilu.git".split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tClone failed!")
                print(result.stdout.decode())
                return False
            chdir(self.working_dir / Path("Lilu"))
            print("\tCloning MacKernelSDK...")
            result = subprocess.run("git clone https://github.com/acidanthera/MacKernelSDK.git".split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tClone of MacKernelSDK failed!")
                print(result.stdout.decode())
                return False
            self._bootstrap_clang32(self.working_dir / Path("Lilu"))
            chdir(self.working_dir / Path("Lilu"))
            print("\tBuilding debug version...")
            result = subprocess.run("xcodebuild -quiet -configuration Debug".split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tBuild failed!")
                print(result.stdout.decode())
                return False
            result = subprocess.run("git rev-parse HEAD".split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tObtaining commit hash failed!")
                print(result.stdout.decode())
                return False
            else:
                commithash = result.stdout.decode().strip()
            shutil.copytree(Path("build/Debug/Lilu.kext"), self.working_dir / Path("Lilu.kext"))
            self.lilu = [commithash, self.working_dir / Path("Lilu.kext")]
        return self.lilu[1]

    def build(self, plugin, commithash=None):
        name = plugin["Name"]
        url = plugin["URL"]
        needs_lilu = plugin.get("Lilu", False)
        needs_mackernelsdk = plugin.get("MacKernelSDK", False)
        fat = plugin.get("32-bit", False)
        edk2 = plugin.get("EDK II", False)
        command = plugin.get("Command")
        prebuild = plugin.get("Pre-Build", [])
        postbuild = plugin.get("Post-Build", [])
        build_opts = plugin.get("Build Opts", [])
        build_dir = plugin.get("Build Dir", "build/")
        p_info = plugin.get("Info", f"{build_dir}Release/{name}.kext/Contents/Info.plist")
        b_type = plugin.get("Type", "Kext")
        d_file = plugin.get("Debug File", f"{build_dir}Debug/*.kext")
        r_file = plugin.get("Release File", f"{build_dir}Release/*.kext")
        extra_files = plugin.get("Extras", None)
        v_cmd = plugin.get("Version", None)

        chdir(self.working_dir)

        if needs_lilu:
            if not self._build_lilu():
                print("Building of prerequiste: Lilu failed!")
                return False

        chdir(self.working_dir)
        print("Building " + name + "...")
        if Path(name).exists():
            shutil.rmtree(Path(name))
        print("\tCloning the repo...")
        result = subprocess.run(["git", "clone", "--recurse-submodules", url + ".git", name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            print("\tClone failed!")
            print(result.stdout.decode())
            return False
        chdir(self.working_dir / Path(name))

        if commithash:
            print("\tChecking out to " + commithash + "...")
            result = subprocess.run(["git", "checkout", commithash], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tCheckout failed!")
                print(result.stdout.decode())
                return False
        else:
            result = subprocess.run("git rev-parse HEAD".split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tObtaining commit hash failed!")
                print(result.stdout.decode())
                return False
            else:
                commithash = result.stdout.decode().strip()
        chdir(self.working_dir / Path(name))

        if needs_lilu:
            lilu_path = self._build_lilu()
            if not lilu_path:
                print("Building of prerequiste: Lilu failed!")
                return False
            shutil.copytree(lilu_path, self.working_dir / Path(name) / Path("Lilu.kext"))

        chdir(self.working_dir / Path(name))
        if needs_mackernelsdk:
            print("\tCloning MacKernelSDK...")
            result = subprocess.run("git clone https://github.com/acidanthera/MacKernelSDK.git".split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tClone of MacKernelSDK failed!")
                print(result.stdout.decode())
                return False

        chdir(self.working_dir / Path(name))
        if fat:
            self._bootstrap_clang32(self.working_dir / Path(name))
            build_opts += ["-arch", "x86_64", "-arch", "ACID32"]

        chdir(self.working_dir / Path(name))
        if edk2:
            self._bootstrap_edk2()

        chdir(self.working_dir / Path(name))
        if prebuild:
            print("\tRunning prebuild tasks...")
            for task in prebuild:
                print("\t\tRunning task '" + task["name"] + "'")
                args = [task["path"]]
                args.extend(task["args"])
                result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                if result.returncode != 0:
                    print("\t\tTask failed!")
                    print(result.stdout.decode())
                    return False
                else:
                    print("\t\tTask completed.")
        chdir(self.working_dir / Path(name))
        if isinstance(command, str) or (isinstance(command, list) and all(isinstance(n, str) for n in command)):
            print("\tBuilding...")
            if isinstance(command, str):
                command = command.split()
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tBuild failed!")
                print(result.stdout.decode())
                print("\tReturn code: " + str(result.returncode))
                return False
        elif isinstance(command, list) and all(isinstance(n, dict) for n in command):
            # Multiple commands
            for i in command:
                print("\t" + i["name"] + "...")
                result = subprocess.run([i["path"]] + i["args"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                if result.returncode != 0:
                    print("\tCommand failed!")
                    print(result.stdout.decode())
                    print("\tReturn code: " + str(result.returncode))
                    return False
        else:
            print("\tBuilding release version...")
            args = "xcodebuild -quiet -configuration Release".split()
            args += build_opts
            args += ["-jobs", "1"]
            # BUILD_DIR should only be added if we don't have scheme. Otherwise, use -derivedDataPath
            args += ["-derivedDataPath", "build"] if "-scheme" in build_opts else ["BUILD_DIR=build/"]

            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tBuild failed!")
                print(result.stdout.decode())
                print("\tReturn code: " + str(result.returncode))
                return False

            print("\tBuilding debug version...")
            args = "xcodebuild -quiet -configuration Debug".split()
            args += build_opts
            args += ["-jobs", "1"]
            # BUILD_DIR should only be added if we don't have scheme. Otherwise, use -derivedDataPath
            args += ["-derivedDataPath", "build"] if "-scheme" in build_opts else ["BUILD_DIR=build/"]

            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tBuild failed!")
                print(result.stdout.decode())
                print("\tReturn code: " + str(result.returncode))
                return False
        chdir(self.working_dir / Path(name))
        if postbuild:
            print("\tRunning postbuild tasks...")
            for task in postbuild:
                print("\t\tRunning task '" + task["name"] + "'")
                args = [task["path"]]
                args.extend(task["args"])
                result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=task.get("cwd", None))
                if result.returncode != 0:
                    print("\t\tTask failed!")
                    print(result.stdout.decode())
                    return False
                else:
                    print("\t\tTask completed.")
        chdir(self.working_dir / Path(name))
        if v_cmd:
            if isinstance(v_cmd, str):
                v_cmd = v_cmd.split()
            result = subprocess.run(v_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                print("\tRunning version command failed!")
                print(result.stdout.decode())
                return False
            else:
                version = result.stdout.decode().strip()
        elif b_type == "Kext":
            plistpath = Path(p_info)
            version = plistlib.load(plistpath.open(mode="rb"))["CFBundleVersion"]
        else:
            print("\tNo version command!")
            return False
        print("\tVersion: " + version)
        category_type = {"Kext": "Kexts", "Bootloader": "Bootloaders", "Utility": "Utilities", "Other": "Others"}[b_type]
        print("\tCopying to build directory...")
        extras = []
        # (extras.extend(self._expand_globs(i)) for i in extra_files) if extra_files is not None else None  # pylint: disable=expression-not-assigned
        if extra_files is not None:
            for i in extra_files:
                extras.extend(self._expand_globs(i))
        debug_file = self._expand_globs(d_file)[0]
        release_file = self._expand_globs(r_file)[0]
        debug_dir = self.build_dir / Path(category_type) / Path(name) / Path(commithash) / Path("Debug")
        release_dir = self.build_dir / Path(category_type) / Path(name) / Path(commithash) / Path("Release")
        for directory in [debug_dir, release_dir]:
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True)
        if extras:
            for i in extras:
                if i.is_dir():
                    print(f"\t{i} is a dir; please fix!")
                    shutil.copytree(i, debug_dir / i.name)
                    shutil.copytree(i, release_dir / i.name)
                elif i.is_file():
                    shutil.copy(i, debug_dir)
                    shutil.copy(i, release_dir)
                elif not i.exists():
                    print(f"\t{i} does not exist!")
                    return False
                else:
                    print(f"\t{i} is not a dir or a file!")
                    continue

        if debug_file.is_dir():
            print(f"{debug_file} is a dir; please fix!")
            shutil.copytree(debug_file, debug_dir / debug_file.name)
        elif debug_file.is_file():
            shutil.copy(debug_file, debug_dir)

        if release_file.is_dir():
            print(f"{release_file} is a dir; please fix!")
            shutil.copytree(release_file, release_dir / release_file.name)
        elif release_file.is_file():
            shutil.copy(release_file, release_dir)

        return {"debug": debug_dir / Path(debug_file.name), "release": release_dir / Path(release_file.name), "extras": [debug_dir / Path(i.name) for i in extras], "version": version}
