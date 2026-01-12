import socket

from autocoder.core.orchestrator import PortAllocator


def _bind_ephemeral() -> tuple[socket.socket, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    return s, s.getsockname()[1]


def test_port_allocator_skips_ports_in_use():
    # Reserve an ephemeral port and keep it bound to simulate a conflicting external process.
    for _ in range(10):
        occupied_socket, occupied_port = _bind_ephemeral()
        if occupied_port < 65000:
            break
        occupied_socket.close()
    else:
        raise AssertionError("Could not acquire a safe ephemeral port for testing")

    # Choose small ranges around ephemeral ports to minimize the chance of collisions.
    for _ in range(10):
        web_socket, web_start = _bind_ephemeral()
        web_socket.close()
        if web_start < 65000:
            break
    else:
        occupied_socket.close()
        raise AssertionError("Could not acquire a safe ephemeral port for testing")

    api_end = min(occupied_port + 25, 65535)
    web_end = min(web_start + 25, 65535)
    assert api_end - occupied_port >= 2
    assert web_end - web_start >= 2

    allocator = PortAllocator(
        api_port_range=(occupied_port, api_end),
        web_port_range=(web_start, web_end),
        verify_availability=True,
    )

    api_port, web_port = allocator.allocate_ports("agent-1")
    assert api_port != occupied_port
    assert allocator.get_agent_ports("agent-1") == (api_port, web_port)

    occupied_socket.close()


def test_claim_next_pending_feature_is_atomic(tmp_path):
    from autocoder.core.database import Database

    db_path = tmp_path / "agent_system.db"
    db = Database(str(db_path))
    for i in range(10):
        db.create_feature(name=f"f{i}", description="d", category="c", priority=0)

    import threading

    claimed: list[int] = []
    lock = threading.Lock()
    barrier = threading.Barrier(10)

    def worker(n: int) -> None:
        local = Database(str(db_path))
        barrier.wait()
        feature = local.claim_next_pending_feature(f"agent-{n}")
        if feature:
            with lock:
                claimed.append(int(feature["id"]))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(claimed) == 10
    assert len(set(claimed)) == 10


def test_clear_feature_in_progress(tmp_path):
    from autocoder.core.database import Database

    db_path = tmp_path / "agent_system.db"
    db = Database(str(db_path))
    feature_id = db.create_feature(name="f", description="d", category="c", priority=0)
    assert db.claim_feature(feature_id, "agent-1", "feat/1")
    assert db.clear_feature_in_progress(feature_id)
    feature = db.get_feature(feature_id)
    assert feature["status"] == "PENDING"


def test_mark_feature_ready_for_verification(tmp_path):
    from autocoder.core.database import Database

    db_path = tmp_path / "agent_system.db"
    db = Database(str(db_path))
    feature_id = db.create_feature(name="f", description="d", category="c", priority=0)
    assert db.claim_feature(feature_id, "agent-1", "feat/1")
    assert db.mark_feature_ready_for_verification(feature_id)
    feature = db.get_feature(feature_id)
    assert feature["status"] == "IN_PROGRESS"
    assert bool(feature["passes"]) is False
    assert feature["review_status"] == "READY_FOR_VERIFICATION"
