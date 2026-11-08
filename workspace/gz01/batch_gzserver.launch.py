"""Reuse installed Gazebo launch arguments/environment; replace only its prefix."""
import importlib.util
from pathlib import Path
import sys

from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    launch_dir = Path(get_package_share_directory('gazebo_ros'))/'launch'
    sys.path.insert(0, str(launch_dir))
    spec = importlib.util.spec_from_file_location('original_gzserver_launch', launch_dir/'gzserver.launch.py')
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    execute_process = original.ExecuteProcess

    def with_batch_prefix(**kwargs):
        kwargs['name'] = 'gzserver'
        kwargs['prefix'] = 'bash ' + str(Path(__file__).with_name('gzserver_gdb.sh'))
        return execute_process(**kwargs)

    original.ExecuteProcess = with_batch_prefix
    return original.generate_launch_description()
