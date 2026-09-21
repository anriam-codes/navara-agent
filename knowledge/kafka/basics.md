# Kafka Basics

## What Kafka is
Apache Kafka is a distributed event log. Producers write messages to topics, and consumers read them. Each topic is split into partitions, and messages inside a partition are strictly ordered. Kafka keeps messages for a retention period (7 days by default), so consumers can re-read them.

## Consumer groups and offsets
Consumers that share the same `group.id` form a consumer group. Kafka assigns each partition to exactly one consumer in the group, so a topic with 3 partitions can be read in parallel by at most 3 consumers in one group. Extra consumers sit idle.

An offset is the position of a consumer in a partition. The committed offset is what Kafka remembers as "processed up to here". If a consumer restarts, it resumes from the committed offset. Consumer lag is the latest offset in a partition minus the committed offset. Growing lag means consumers are slower than producers.

## Listeners and advertised.listeners
This is the most common source of Kafka connection problems.
- `listeners` is the address and port the broker binds to and accepts connections on.
- `advertised.listeners` is the address the broker tells clients to use after the first connection.

A client connects to the bootstrap server, and the broker replies with its advertised address. The client then reconnects to that advertised address. If the advertised address is not reachable from the client, the connection fails even though the first connection succeeded.

Example for Kafka running in Docker, with one listener for containers and one for the host machine:

```
KAFKA_LISTENERS=INTERNAL://0.0.0.0:29092,EXTERNAL://0.0.0.0:9092
KAFKA_ADVERTISED_LISTENERS=INTERNAL://kafka:29092,EXTERNAL://localhost:9092
```

Containers in the same Docker network connect to `kafka:29092`. Applications on the host machine connect to `localhost:9092`.

## Important configuration
| Setting | Side | Meaning |
|---|---|---|
| `bootstrap.servers` | Client | Initial broker addresses used to discover the cluster |
| `group.id` | Consumer | Identifies the consumer group |
| `auto.offset.reset` | Consumer | `earliest` or `latest`. Where to start when the group has no committed offset. Default is `latest` |
| `enable.auto.commit` | Consumer | Commit offsets automatically in the background. Default is true |
| `max.poll.interval.ms` | Consumer | Max time between `poll()` calls before the consumer is removed from the group. Default is 300000 (5 min) |
| `session.timeout.ms` | Consumer | Time without a heartbeat before the consumer is considered dead |
| `max.message.bytes` | Broker/topic | Largest message the broker accepts. Default is about 1 MB |
| `retention.ms` | Topic | How long messages are kept |