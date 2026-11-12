"""Read sealed ns-3.40 DLT105 PCAPs; never starts a model or controls a device.

The pinned ns-3 A-MPDU delimiter is LE16 length/EOF, CRC=1, signature=0x4e.
MPDU lengths include their four-byte MAC trailer; padding precedes the next
delimiter. These captures are ns-3 MAC headers, not radiotap or Linux sockets.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct


def decode(path, cap):
    counts = Counter()
    totals, payloads, tcp_headers, tcp_flags, flows = (Counter() for _ in range(5))
    examples, problems = [], []

    def problem(reason, record, **context):
        counts['unresolved'] += 1
        if len(problems) < 12:
            problems.append(dict(record=record, reason=reason, **context))

    def mpdu(data, record):
        if len(data) < 10:
            raise ValueError('short MAC header')
        fc = struct.unpack_from('<H', data)[0]
        version, kind, subtype = fc & 3, (fc >> 2) & 3, (fc >> 4) & 15
        if version:
            raise ValueError('unknown MAC version')
        counts['MPDU'] += 1
        if kind in (0, 1):
            counts['management' if kind == 0 else 'control'] += 1
            return
        if kind != 2:
            raise ValueError('unknown MAC type')
        counts['data_MAC'] += 1
        header = 24 + (6 if fc & 0x300 == 0x300 else 0)
        qos = bool(subtype & 8)
        if len(data) < header + (2 if qos else 0) + 4:
            raise ValueError('short data MAC header/trailer')
        if fc & 0x400 or struct.unpack_from('<H', data, 22)[0] & 15:
            raise ValueError('unresolved MAC fragmentation')
        if fc & 0x4000:
            raise ValueError('unresolved protected data')
        if qos:
            if data[header] & 0x80:
                raise ValueError('unresolved A-MSDU data')
            header += 2
        # The actual ns-3.40 WifiMacHeader serializer has no HT-control field.
        body = data[header:-4]
        if subtype & 4:
            if body:
                raise ValueError('nonempty NULL data subtype')
            counts['null_data'] += 1
            return
        if len(body) < 8 or body[:6] != b'\xaa\xaa\x03\x00\x00\x00':
            raise ValueError('unknown data LLC/SNAP')
        ethertype = int.from_bytes(body[6:8], 'big')
        ip = body[8:]
        if ethertype == 0x806:
            if len(ip) < 28:
                raise ValueError('short ARP')
            counts['ARP'] += 1
            return
        if ethertype != 0x800:
            raise ValueError('unknown data EtherType ' + hex(ethertype))
        if len(ip) < 20 or ip[0] >> 4 != 4:
            raise ValueError('short/non-v4 IP header')
        ihl = (ip[0] & 15) * 4
        total = int.from_bytes(ip[2:4], 'big')
        if ihl < 20 or total < ihl or len(ip) != total:
            raise ValueError('IP header/total extent mismatch')
        counts['IPv4'] += 1
        totals[total] += 1
        frag = int.from_bytes(ip[6:8], 'big')
        if frag & 0x2000:
            counts['IPv4_MF'] += 1
        if frag & 0x1fff:
            counts['IPv4_nonzero_fragment_offset'] += 1
        if total > 1500:
            counts['IPv4_total_over_1500'] += 1
        if frag & 0x3fff:
            return  # Honest fragment counters; never decode a partial TCP header.
        if ip[9] != 6:
            problem('Non-TCP IPv4 not part of expected fixture', record, protocol=ip[9])
            return
        tcp = ip[ihl:total]
        if len(tcp) < 20:
            raise ValueError('short TCP header')
        size = (tcp[12] >> 4) * 4
        if size < 20 or size > len(tcp):
            raise ValueError('TCP data offset invalid')
        flags = tcp[13]
        counts['TCP'] += 1
        tcp_flags[flags] += 1
        payload = len(tcp) - size
        options, cursor = [], 20
        while cursor < size:
            option = tcp[cursor]
            if option == 0:
                break
            if option == 1:
                cursor += 1
                continue
            if cursor + 2 > size or tcp[cursor+1] < 2 or cursor + tcp[cursor+1] > size:
                raise ValueError('malformed TCP option')
            options.append((option, tcp[cursor+1]))
            cursor += tcp[cursor+1]
        if payload and not flags & 2:
            counts['ordinary_TCP_data'] += 1
            payloads[payload] += 1
            tcp_headers[size] += 1
            if size != 32:
                counts['ordinary_data_header_not32'] += 1
            if (8, 10) not in options:
                counts['ordinary_data_without_timestamp'] += 1
            if payload > cap:
                counts['ordinary_payload_over_cap'] += 1
            if payload == cap:
                counts['full_cap_payload_observed'] += 1
            src = '.'.join(map(str, ip[12:16]))
            dst = '.'.join(map(str, ip[16:20]))
            ports = struct.unpack_from('!HH', tcp)
            flows[f'{src}:{ports[0]}->{dst}:{ports[1]}'] += 1
        if len(examples) < 3:
            examples.append(dict(record=record, fc=hex(fc), MAC_header=header,
                IP_ihl=ihl, IP_total=total, fragment_field=frag,
                TCP_header=size, payload=payload, TCP_flags=flags, options=options))

    with path.open('rb') as stream:
        gh = stream.read(24)
        if len(gh) != 24 or gh[:4] != b'\xd4\xc3\xb2\xa1':
            raise ValueError('Expected little-endian microsecond PCAP')
        _, major, minor, _, _, snaplen, dlt = struct.unpack('<IHHIIII', gh)
        if (major, minor, dlt) != (2, 4, 105):
            raise ValueError('Expected PCAP2.4 DLT105 IEEE802_11')
        while record_header := stream.read(16):
            if len(record_header) != 16:
                raise ValueError('truncated PCAP record header')
            sec, usec, included, original = struct.unpack('<IIII', record_header)
            counts['records'] += 1
            data = stream.read(included)
            if len(data) != included or included != original or included > snaplen:
                raise ValueError('truncated PCAP packet')
            try:
                if len(data) >= 4 and data[2:4] == b'\x01\x4e':
                    counts['A_MPDU_records'] += 1
                    cursor = 0
                    while cursor < len(data):
                        if len(data)-cursor < 4 or data[cursor+2:cursor+4] != b'\x01\x4e':
                            raise ValueError('invalid A-MPDU delimiter')
                        field = struct.unpack_from('<H', data, cursor)[0]
                        length = field & 0x3fff
                        end = cursor + 4 + length
                        if length < 10 or end > len(data):
                            raise ValueError('invalid delimiter MPDU extent')
                        mpdu(data[cursor+4:end], counts['records'])
                        counts['A_MPDU_subframes'] += 1
                        cursor = end
                        if cursor != len(data):
                            padding = (-cursor) % 4
                            if data[cursor:cursor+padding] != b'\0' * padding:
                                raise ValueError('nonzero A-MPDU padding')
                            cursor += padding
                else:
                    counts['bare_MAC_records'] += 1
                    mpdu(data, counts['records'])
            except ValueError as error:
                problem(str(error), counts['records'], prefix=data[:40].hex())
    checks = dict(actual_IP_and_ordinary_TCP_present=counts['IPv4'] > 0 and counts['ordinary_TCP_data'] > 0,
        no_unresolved=counts['unresolved'] == 0,
        all_IP_total_at_most1500=counts['IPv4_total_over_1500'] == 0,
        no_IP_MF_or_offset=counts['IPv4_MF'] == 0 and counts['IPv4_nonzero_fragment_offset'] == 0,
        ordinary_data_header32_and_TS=counts['ordinary_data_header_not32'] == 0 and counts['ordinary_data_without_timestamp'] == 0,
        payload_at_most_cap_and_full_segment_seen=counts['ordinary_payload_over_cap'] == 0 and counts['full_cap_payload_observed'] > 0,
        all_six_business_TCP_directions_present=len(flows) == 6)
    return dict(path=str(path), cap=cap, status='PASS_PACKETIZATION_ONLY' if all(checks.values()) else 'FAIL_OR_UNRESOLVED',
        checks=checks, counts=dict(counts), IP_total_histogram=dict(totals), ordinary_payload_histogram=dict(payloads),
        ordinary_header_histogram=dict(tcp_headers), TCP_flag_histogram=dict(tcp_flags),
        flows=dict(flows), first_IP_examples=examples, problems=problems,
        limits='Capture records include duplicate PHY observations/retries; counts are not unique packets. PCAP simulation timestamps are not wall-clock time.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cap', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('pcap', type=Path, nargs='+')
    args = parser.parse_args()
    rows = [decode(path, args.cap) for path in args.pcap]
    with args.output.open('x') as f:
        json.dump(dict(status='PASS_PACKETIZATION_ONLY' if all(x['status']=='PASS_PACKETIZATION_ONLY' for x in rows) else 'FAIL_OR_UNRESOLVED', files=rows), f, indent=2)
        f.write('\n')
    print(json.dumps([dict(path=x['path'],status=x['status'],checks=x['checks'],counts=x['counts'],problems=x['problems'][:2]) for x in rows],indent=2))
