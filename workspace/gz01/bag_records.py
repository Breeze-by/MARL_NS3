"""Read every recorded sqlite shard in actual timestamp order, without ROS init."""
from contextlib import ExitStack, closing
import heapq
from pathlib import Path
import sqlite3
import yaml


def records(directory):
    directory=Path(directory)
    metadata=yaml.safe_load((directory/'metadata.yaml').read_text())['rosbag2_bagfile_information']
    if metadata['storage_identifier']!='sqlite3':
        raise ValueError('GZ-01 offline reader expects recorded sqlite3 storage')
    with ExitStack() as stack:
        iterators=[]
        for shard,relative in enumerate(metadata['relative_file_paths']):
            connection=stack.enter_context(closing(sqlite3.connect('file:'+str(directory/relative)+'?mode=ro',uri=True)))
            topics={i:(name,type_) for i,name,type_ in connection.execute('SELECT id,name,type FROM topics')}
            def rows(connection=connection,topics=topics,shard=shard):
                for identity,topic,timestamp,data in connection.execute('SELECT id,topic_id,timestamp,data FROM messages ORDER BY timestamp,id'):
                    yield timestamp,shard,identity,*topics[topic],data
            iterators.append(rows())
        for timestamp,shard,identity,name,type_,data in heapq.merge(*iterators,key=lambda row:row[:3]):
            yield name,type_,timestamp,data
