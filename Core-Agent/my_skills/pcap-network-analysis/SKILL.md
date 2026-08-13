---
name: pcap-network-analysis
description: "Parse PCAP files and compute network traffic statistics using scapy. Use when analyzing network packet captures for protocol counts, traffic entropy, graph metrics (nodes/edges/density), time-series rate statistics, or intrusion detection patterns. Covers Shannon entropy, directed IP graph construction, packets-per-minute bucketing, and protocol splitting with scapy."
---

# PCAP Network Analysis with Scapy

## Overview

This skill covers parsing `.pcap` files and computing network traffic statistics using Python's `scapy` library. Typical outputs include protocol counts, traffic entropy, directed IP graph metrics, time-series rate statistics, and threat detection.

## Loading Packets

```python
from scapy.all import rdpcap, IP, TCP, UDP, ICMP, ARP

packets = rdpcap('/root/packets.pcap')
```

**scapy is pre-installed** in the Docker environment for cybersecurity tasks. If not, install with `pip install scapy`.

## Protocol Splitting

```python
tcp_pkts = [p for p in packets if TCP in p]
udp_pkts = [p for p in packets if UDP in p]
icmp_pkts = [p for p in packets if ICMP in p]
arp_pkts = [p for p in packets if ARP in p]
ip_pkts  = [p for p in packets if IP in p]   # IP layer present (includes TCP+UDP+ICMP)
```

**Key**: `protocol_ip_total` counts packets with an IP layer, NOT total packets. ARP packets have no IP layer.

## Time / Rate Statistics

```python
import math
from collections import defaultdict

timestamps = sorted(float(p.time) for p in packets if hasattr(p, 'time'))
duration = timestamps[-1] - timestamps[0]

# Packets per minute: bucket by 60-second windows
start_time = timestamps[0]
minute_buckets = defaultdict(int)
for ts in timestamps:
    minute = int((ts - start_time) / 60)
    minute_buckets[minute] += 1

ppm_values = list(minute_buckets.values())
ppm_avg = sum(ppm_values) / len(ppm_values)
ppm_max = max(ppm_values)
ppm_min = min(ppm_values)
```

## Packet Size Statistics

```python
sizes = [len(p) for p in packets]
total_bytes = sum(sizes)
avg_size = sum(sizes) / len(sizes)
min_size = min(sizes)
max_size = max(sizes)
```

## Shannon Entropy

Shannon entropy over a frequency distribution: `H(X) = -Σ p(x) * log₂(p(x))`

```python
from collections import Counter

def shannon_entropy(counter):
    """Shannon entropy in bits from a Counter of frequencies."""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return round(entropy, 4)

# Source/destination IP entropy
src_ips = Counter(p[IP].src for p in ip_pkts)
dst_ips = Counter(p[IP].dst for p in ip_pkts)
src_ip_entropy = shannon_entropy(src_ips)
dst_ip_entropy = shannon_entropy(dst_ips)

# Source/destination port entropy (TCP + UDP only)
src_ports = Counter()
dst_ports = Counter()
for p in packets:
    if TCP in p:
        src_ports[p[TCP].sport] += 1
        dst_ports[p[TCP].dport] += 1
    elif UDP in p:
        src_ports[p[UDP].sport] += 1
        dst_ports[p[UDP].dport] += 1

src_port_entropy = shannon_entropy(src_ports)
dst_port_entropy = shannon_entropy(dst_ports)
unique_src_ports = len(src_ports)
unique_dst_ports = len(dst_ports)
```

**Key**: Entropy is computed over the **frequency distribution** of observed values, not over raw packets. Use `Counter` to count occurrences, then apply the formula.

## Directed IP Graph Metrics

Nodes = distinct IP addresses (from src OR dst). Edges = unique directed (src → dst) pairs.

```python
edges = set()
indegree = defaultdict(set)   # dst → set of src IPs
outdegree = defaultdict(set)  # src → set of dst IPs

for p in ip_pkts:
    src, dst = p[IP].src, p[IP].dst
    edges.add((src, dst))
    outdegree[src].add(dst)
    indegree[dst].add(src)

all_nodes = set(indegree.keys()) | set(outdegree.keys())
num_nodes = len(all_nodes)
num_edges = len(edges)

# Network density: directed graph formula
if num_nodes >= 2:
    network_density = num_edges / (num_nodes * (num_nodes - 1))
else:
    network_density = 0.0

# max_outdegree: max distinct destinations contacted by any single source
max_outdegree = max(len(v) for v in outdegree.values()) if outdegree else 0

# max_indegree: max distinct sources contacting any single destination
max_indegree = max(len(v) for v in indegree.values()) if indegree else 0
```

### ⚠️ CRITICAL: Count UNIQUE IPs, Not Packets

- `num_nodes` = count of **distinct** IP addresses, NOT total packets
- `num_edges` = count of **unique** (src, dst) pairs, NOT total packets
- `max_outdegree` = max **distinct** destinations, NOT packet count to one destination

Using `len(packets)` instead of `len(set(...))` will give wildly wrong numbers.

### ⚠️ CRITICAL: Directed vs Undirected

The graph is **directed**: (A→B) ≠ (B→A). Both are separate edges. The density formula uses `n*(n-1)` (directed), NOT `n*(n-1)/2` (undirected).

## Threat Detection Thresholds

### Port Scan — ALL THREE conditions must be met:

| Condition        | Threshold   |
|-----------------|-------------|
| Port Entropy    | > 6.0 bits  |
| SYN-only Ratio  | > 0.7 (70%) |
| Unique Ports    | > 100       |

SYN-only = TCP SYN flag (0x02) without ACK (0x10): `flags & 0x02 and not (flags & 0x10)`

### DoS Pattern:

```
Ratio = packets_per_minute_max / packets_per_minute_avg
DoS detected if: Ratio > 20
```
Ratios of 5x-15x are normal traffic variation, NOT DoS.

### C2 Beaconing:

```
IAT CV (Coefficient of Variation) = std(inter_arrival_times) / mean(inter_arrival_times)
Beaconing detected if: CV < 0.5
```

## Common Mistakes

- **Counting packets instead of unique IPs/edges for graph metrics.** `num_nodes` is distinct IPs, not packet count.
- **Using undirected density formula `n*(n-1)/2` for a directed graph.** The correct denominator is `n*(n-1)`.
- **Including ARP packets in IP-based counts.** ARP has no IP layer — check `IP in p` first.
- **Computing entropy on raw packets instead of frequency distribution.** Must use `Counter` first, then apply `H = -Σ p*log2(p)`.
- **Using `len(minute_buckets)` instead of actual bucket values for ppm stats.** Buckets may not be contiguous; use the actual counts.
- **Forgetting to handle the `duration_seconds = 0` edge case.** If all packets have the same timestamp, duration is 0 — avoid division by zero.
- **Mixing up src/dst port entropy with unique port counts.** Entropy and unique count are different metrics — compute both separately.
- **Detecting port scan on high port count alone.** Must check ALL THREE conditions (entropy > 6, SYN ratio > 0.7, unique ports > 100).

## Sanity Checks

- `protocol_ip_total <= len(packets)` (IP packets are a subset of all packets)
- `protocol_tcp + protocol_udp + protocol_icmp <= protocol_ip_total` (these all have IP layers)
- `network_density` is between 0 and 1
- `max_outdegree <= num_nodes - 1` (can't contact more destinations than total nodes)
- `shannon_entropy` is >= 0 and <= log2(number of unique values)
- All entropy values should be reasonable (not NaN, not negative)
