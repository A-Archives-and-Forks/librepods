import asyncio
import os
import logging

logger = logging.getLogger("channel_extensions")

try:
    from bumble.l2cap import ClassicChannel as _ClassicChannel  # type: ignore
except Exception:
    _ClassicChannel = None

def _make_reader(ch):
    """
    Return a tuple (reader_callable, restore_callable_or_None).
    The reader_callable is an async function that returns the next bytes/SDU.
    If the implementation requires installing a sink, restore_callable will
    undo that change (restore previous sink) when called.
    """
    if ch is None:
        async def _none_read():
            raise RuntimeError("Channel implementation not available")
        return _none_read, None

    # Prefer explicit read-style APIs if available
    for name in ("receive", "recv", "read"):
        fn = getattr(ch, name, None)
        if fn is not None:
            if asyncio.iscoroutinefunction(fn):
                async def _reader():
                    return await fn()
                return _reader, None
            else:
                async def _reader():
                    return fn()
                return _reader, None

    # Fallback: if the channel exposes a 'sink' attribute, install a queue sink
    if hasattr(ch, "sink"):
        recv_q: asyncio.Queue = asyncio.Queue()
        old_sink = getattr(ch, "sink", None)

        # create sink that pushes incoming SDUs into queue
        def _sink(sdu):
            try:
                recv_q.put_nowait(sdu)
            except Exception:
                # best-effort; if queue full or closed, drop
                logger.debug("Dropping SDU in sink fallback")

        # attach the sink
        try:
            ch.sink = _sink
        except Exception:
            # if sink can't be set, fall through to error reader
            logger.debug("Failed to set channel.sink fallback")

        async def _reader_from_sink():
            item = await recv_q.get()
            return item

        def _restore_sink():
            try:
                if old_sink is None:
                    try:
                        delattr(ch, "sink")
                    except Exception:
                        pass
                else:
                    ch.sink = old_sink
            except Exception:
                logger.exception("Failed to restore original channel.sink")

        return _reader_from_sink, _restore_sink

    # No read-like API found
    async def _no_read():
        raise RuntimeError("No read method found on channel")
    return _no_read, None

def _make_writer(ch):
    """
    Return an async callable that writes bytes to the channel.
    Tries common method names used by different APIs.
    """
    if ch is None:
        async def _none_write(_data: bytes):
            raise RuntimeError("Channel implementation not available")
        return _none_write

    for name in ("send", "write", "send_pdu"):
        fn = getattr(ch, name, None)
        if fn is not None:
            if asyncio.iscoroutinefunction(fn):
                async def _writer(data: bytes):
                    await fn(data)
                return _writer
            else:
                async def _writer(data: bytes):
                    fn(data)
                return _writer
    async def _no_write(_data: bytes):
        raise RuntimeError("No write method found on channel")
    return _no_write

if _ClassicChannel is not None:
    async def bridge_to_unix_socket(self, path: str, *, backlog: int = 1):
        """
        Bridge this classic L2CAP channel to a UNIX domain socket at `path`.
        Creates a server socket and accepts a single client connection, then
        forwards bytes bidirectionally until EOF / disconnect.
        Usage:
            await channel.bridge_to_unix_socket("/tmp/smth.sock")
        """
        # remove stale socket file
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            logger.exception("Failed to remove existing socket file %s", path)

        loop = asyncio.get_running_loop()
        conn_event = asyncio.Event()
        client = {}

        async def _client_cb(reader, writer):
            client["reader"] = reader
            client["writer"] = writer
            conn_event.set()
            # keep handler alive until server is closed
            await conn_event.wait()

        server = await asyncio.start_unix_server(_client_cb, path=path, backlog=backlog)
        logger.info("L2CAP bridge listening on %s", path)

        # Wait for one client
        try:
            await conn_event.wait()
            reader = client["reader"]
            writer = client["writer"]
        except Exception:
            server.close()
            await server.wait_closed()
            raise

        # get reader and optional restore callback
        read_channel, read_restore = _make_reader(self)
        write_channel = _make_writer(self)

        async def chan_to_sock():
            try:
                while True:
                    data = await read_channel()
                    if not data:
                        break
                    # some channel APIs return memoryview; ensure bytes
                    if not isinstance(data, (bytes, bytearray)):
                        try:
                            data = bytes(data)
                        except Exception:
                            logger.warning("Received non-bytes data from channel, dropping")
                            continue
                    writer.write(data)
                    await writer.drain()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Error in channel->socket bridge, closing connection")
                logger.debug(e)
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        async def sock_to_chan():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    # ensure bytes
                    if not isinstance(data, (bytes, bytearray)):
                        try:
                            data = bytes(data)
                        except Exception:
                            logger.warning("Received non-bytes data from socket, dropping")
                            continue
                    await write_channel(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in socket->channel bridge")
            finally:
                # attempt to close channel if it has a close/cancel method
                close_fn = getattr(self, "close", None)
                if close_fn is not None:
                    try:
                        if asyncio.iscoroutinefunction(close_fn):
                            await close_fn()
                        else:
                            close_fn()
                    except Exception:
                        logger.exception("Failed to close channel")

        tasks = [
            asyncio.create_task(chan_to_sock(), name="chan_to_sock"),
            asyncio.create_task(sock_to_chan(), name="sock_to_chan"),
        ]

        # Wait until either task completes
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
            try:
                await t
            except Exception:
                pass

        # cleanup server and socket file
        try:
            conn_event.set()  # allow handler to finish
            server.close()
            await server.wait_closed()
        except Exception:
            logger.exception("Error closing unix server")
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            logger.exception("Failed to remove socket file %s", path)

        # restore reader sink if needed
        try:
            if read_restore is not None:
                read_restore()
        except Exception:
            logger.exception("Failed to restore channel reader state")

    # attach the method to the ClassicChannel class
    setattr(_ClassicChannel, "bridge_to_unix_socket", bridge_to_unix_socket)

else:
    logger.info("bumble.l2cap.ClassicChannel not available; bridge method not attached")

