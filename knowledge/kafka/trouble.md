# Kafka Troubleshooting

## Kafka connection refused on localhost:9092
**Symptom:** A Kafka producer or consumer fails with `Connection refused`, `NoBrokersAvailable`, or `Connection to node -1 (localhost/127.0.0.1:9092) could not be established`.

**Causes:**
- The Kafka broker is not running or crashed on startup.
- The client uses the wrong host or port.
- The Kafka client runs inside a Docker container and `localhost` points to the container itself, not the broker.
- `advertised.listeners` advertises an address the client cannot reach.

**Diagnose:**
1. Check the broker is running: `docker ps` and `docker logs kafka --tail 50`.
2. Test the port from the client machine: `nc -zv localhost 9092`.
3. Compare the client's `bootstrap.servers` with the broker's `advertised.listeners`.

**Fix:**
- Start the broker if it is stopped.
- If the client runs in a container, use the Kafka service name and its internal listener port (for example `kafka:29092`) instead of `localhost:9092`.
- Configure separate internal and external listeners so both host and container clients can connect.

## Kafka consumer keeps rebalancing
**Symptom:** A Kafka consumer logs `Attempt to heartbeat failed since group is rebalancing`, or repeated `Revoking previously assigned partitions` and `Member ... sending LeaveGroup request`. Consumers keep joining and leaving the group and little work gets done.

**Causes:**
- Message processing takes longer than `max.poll.interval.ms`, so Kafka assumes the consumer is dead and removes it.
- A consumer instance keeps crashing and restarting.
- `session.timeout.ms` is too low for the network or GC pauses.

**Diagnose:**
1. Measure how long processing one batch takes and compare it to `max.poll.interval.ms` (default 5 minutes).
2. Look for `CommitFailedException` in the consumer logs, which usually means the consumer was already removed from the group.
3. Check the consumer application for restarts.

**Fix:**
- Lower `max.poll.records` so each batch finishes faster.
- Raise `max.poll.interval.ms` if slow processing is expected.
- Move slow work out of the poll loop into a worker thread or queue.

## Kafka consumer receives no messages
**Symptom:** A Kafka consumer starts without errors and connects to the broker, but never receives any messages even though the topic contains data.

**Causes:**
- `auto.offset.reset` is `latest` (the default), and the consumer group is new, so it only sees messages produced after it starts.
- The consumer group already has committed offsets at the end of the topic.
- The consumer subscribed to the wrong topic name.
- More consumers than partitions in the group, so this consumer has no partition assigned.

**Diagnose:**
1. Describe the group: `kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group <group>`.
2. Compare `CURRENT-OFFSET` and `LOG-END-OFFSET`.
3. Confirm the topic name and partition count with `kafka-topics.sh --describe`.

**Fix:**
- Set `auto.offset.reset=earliest` for a new group that should read old data.
- To replay an existing group, reset offsets: `kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group <group> --topic <topic> --reset-offsets --to-earliest --execute` (stop the consumers first).

## Kafka consumer lag keeps growing
**Symptom:** Kafka consumer lag increases over time and consumers process messages long after they were produced.

**Causes:**
- Consumers process messages slower than producers write them.
- Too few partitions to parallelize the consumers.
- Slow downstream calls (database writes, HTTP requests) inside the consumer loop.
- Frequent rebalances stopping consumption.

**Diagnose:**
1. Check lag per partition with `kafka-consumer-groups.sh --describe`. If only one partition lags, look for a hot key.
2. Profile the consumer's per-message processing time.

**Fix:**
- Add consumers, up to the partition count.
- Increase partitions if you need more parallelism (this changes key-to-partition mapping).
- Batch database writes and make downstream calls asynchronous.

## Kafka LEADER_NOT_AVAILABLE error
**Symptom:** A producer logs `LEADER_NOT_AVAILABLE` or `Error while fetching metadata ... LEADER_NOT_AVAILABLE`, often right after the first message to a new topic.

**Causes:**
- The topic was just auto-created and partition leaders are still being elected.
- The broker hosting the partition leader is down.
- Auto topic creation is disabled and the topic does not exist.

**Diagnose:**
1. List topics: `kafka-topics.sh --bootstrap-server localhost:9092 --list`.
2. Describe the topic and check that each partition shows a `Leader` that is not `-1`.

**Fix:**
- Retry. On a new auto-created topic the error usually disappears after a few seconds.
- Create the topic explicitly before producing.
- Restart the failed broker if a leader is missing.

## Kafka RecordTooLargeException message too large
**Symptom:** A producer fails with `RecordTooLargeException: The message is 2097240 bytes when serialized which is larger than 1048576`, or the broker returns `MESSAGE_TOO_LARGE`.

**Causes:**
- The message exceeds the producer's `max.request.size` or the broker/topic `max.message.bytes` (both about 1 MB by default).

**Diagnose:**
- Compare the message size to `max.request.size` on the producer and `max.message.bytes` on the topic.

**Fix:**
- Prefer sending less data: store large payloads in object storage and send only a reference.
- Otherwise raise `max.request.size` on the producer and `max.message.bytes` on the topic, and make sure consumers' `fetch.max.bytes` and `max.partition.fetch.bytes` are large enough.# Kafka Troubleshooting
