"""Synthetic storage test only, no ROS messages, simulator or robot calls."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from bag_records import records


class ShardTests(unittest.TestCase):
    def test_metadata_shards_and_late_final_coverage_record(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            (directory/'metadata.yaml').write_text('rosbag2_bagfile_information:\n  storage_identifier: sqlite3\n  relative_file_paths: [bag_10.db3, bag_2.db3]\n')
            for name,rows in [('bag_2.db3',[(1,1,20,b'initial_map'),(2,1,40,b'later_map')]),
                              ('bag_10.db3',[(1,1,30,b'feedback'),(2,1,600,b'final_coverage')])]:
                connection=sqlite3.connect(directory/name)
                connection.execute('CREATE TABLE topics(id INTEGER,name TEXT,type TEXT)')
                connection.execute('INSERT INTO topics VALUES(1,"/merge_map","fixture")')
                connection.execute('CREATE TABLE messages(id INTEGER,topic_id INTEGER,timestamp INTEGER,data BLOB)')
                connection.executemany('INSERT INTO messages VALUES(?,?,?,?)',rows)
                connection.commit();connection.close()
            result=list(records(directory))
            self.assertEqual([r[2] for r in result],[20,30,40,600])
            self.assertEqual(result[-1][3],b'final_coverage')


if __name__=='__main__':unittest.main()
