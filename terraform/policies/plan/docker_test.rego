package main

import rego.v1

safe_container := {
  "address": "module.persistence.docker_container.postgres",
  "mode": "managed", "type": "docker_container", "name": "postgres",
  "change": {
    "actions": ["create"], "after_unknown": {},
    "after": {
      "name": "fixture-postgres", "image": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "privileged": false, "network_mode": "bridge", "publish_all_ports": false,
      "ports": [], "mounts": [],
      "volumes": [{"container_path": "/var/lib/postgresql/data", "volume_name": "fixture-postgres-data"}],
    },
  },
}

safe_image := {
  "address": "module.persistence.docker_image.postgres",
  "mode": "managed", "type": "docker_image", "name": "postgres",
  "change": {"actions": ["create"], "after_unknown": {}, "after": {
    "name": "example.invalid/postgres@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  }},
}

safe_plan := {
  "format_version": "1.2",
  "resource_changes": [safe_container, safe_image],
  "configuration": {"root_module": {"module_calls": {"persistence": {"module": {
    "resources": [{"address": "docker_container.postgres", "expressions": {
      "image": {"references": ["docker_image.postgres.image_id", "docker_image.postgres"]},
    }}],
  }}}}},
}

# Centraliza el sobre del plan para que cada caso cambie solo el dato de seguridad.
plan_with(values, unknown) := object.union(safe_plan, {"resource_changes": [
  object.union(safe_container, {"change": {"after": values, "after_unknown": unknown, "actions": ["create"]}}),
  safe_image,
]})

test_accept_safe_plan if {
  violations := deny with input as safe_plan
  count(violations) == 0
}

test_reject_unsafe_container if {
  cases := {
    "privileged": {"patch": {"privileged": true}, "code": "P003:"},
    "host_network": {"patch": {"network_mode": "host"}, "code": "P004:"},
    "host_pid": {"patch": {"pid_mode": "host"}, "code": "P004:"},
    "host_ipc": {"patch": {"ipc_mode": "host"}, "code": "P004:"},
    "publish_all": {"patch": {"publish_all_ports": true}, "code": "P005:"},
    "database_port": {"patch": {"ports": [{"internal": 5432, "ip": "127.0.0.1"}]}, "code": "P006:"},
    "redis_port": {"patch": {"ports": [{"internal": 6379, "ip": "127.0.0.1"}]}, "code": "P006:"},
    "socket_volume": {"patch": {"volumes": [{"host_path": "/var/run/docker.sock"}]}, "code": "P007:"},
    "socket_mount": {"patch": {"mounts": [{"type": "bind", "source": "/var/run/docker.sock"}]}, "code": "P007:"},
    "socket_directory": {"patch": {"mounts": [{"type": "bind", "source": "/var/run"}]}, "code": "P007:"},
    "windows_pipe": {"patch": {"mounts": [{"type": "bind", "source": `//./pipe/docker_engine`}]}, "code": "P007:"},
    "missing_volume": {"patch": {"volumes": []}, "code": "P008:"},
    "anonymous_volume": {"patch": {"volumes": [{"container_path": "/var/lib/postgresql/data", "volume_name": ""}]}, "code": "P008:"},
    "bind_data": {"patch": {"volumes": [{"container_path": "/var/lib/postgresql/data", "host_path": "/tmp/db"}]}, "code": "P008:"},
    "mutable_container_image": {"patch": {"image": "postgres:latest"}, "code": "P010:"},
  }
  every _, case in cases {
    values := object.union(safe_container.change.after, case.patch)
    candidate := plan_with(values, {})
    violations := deny with input as candidate
    some violation in violations
    startswith(violation, case.code)
  }
}

test_reject_unknown_security_values if {
  every field in {"ports", "privileged", "network_mode", "publish_all_ports", "pid_mode", "ipc_mode", "volumes", "mounts"} {
    candidate := plan_with(safe_container.change.after, {field: true})
    violations := deny with input as candidate
    some violation in violations
    startswith(violation, "P011:")
  }
}

test_reject_nested_unknown if {
  candidate := plan_with(safe_container.change.after, {"ports": [{"ip": true}]})
  violations := deny with input as candidate
  some violation in violations
  startswith(violation, "P011:")
}

test_accept_unknown_managed_image if {
  candidate := plan_with(object.union(safe_container.change.after, {"image": null}), {"image": true})
  violations := deny with input as candidate
  count(violations) == 0
}

test_reject_unknown_unmanaged_image if {
  candidate := object.remove(plan_with(object.union(safe_container.change.after, {"image": null}), {"image": true}), ["configuration"])
  violations := deny with input as candidate
  some violation in violations
  startswith(violation, "P010:")
}

test_accept_indexed_module_reference if {
  container := object.union(safe_container, {"address": `module.persistence["lab"].docker_container.postgres[0]`, "change": {
    "after": object.union(safe_container.change.after, {"image": null}), "after_unknown": {"image": true},
  }})
  candidate := object.union(safe_plan, {"resource_changes": [container, safe_image]})
  violations := deny with input as candidate
  count(violations) == 0
}

test_reject_mutable_image if {
  every tag in {"postgres", "postgres:latest", "registry.invalid:5000/postgres:16", "postgres@sha256:abc"} {
    image := object.union(safe_image, {"change": {"after": {"name": tag}, "after_unknown": {}}})
    candidate := object.union(safe_plan, {"resource_changes": [safe_container, image]})
    violations := deny with input as candidate
    some violation in violations
    startswith(violation, "P009:")
  }
}

test_reject_unknown_image_digest if {
  image := object.union(safe_image, {"change": {"after": {}, "after_unknown": {"name": true}}})
  candidate := object.union(safe_plan, {"resource_changes": [safe_container, image]})
  violations := deny with input as candidate
  some violation in violations
  startswith(violation, "P011:")
}

test_accept_named_mount if {
  values := object.union(safe_container.change.after, {"volumes": [], "mounts": [{"type": "volume", "source": "fixture-data", "target": "/var/lib/postgresql/data"}]})
  candidate := plan_with(values, {})
  violations := deny with input as candidate
  count(violations) == 0
}

test_storage_recognizes_container_suffix if {
  container := object.union(safe_container, {"name": "service", "change": {"after": object.union(safe_container.change.after, {"volumes": []})}})
  candidate := object.union(safe_plan, {"resource_changes": [container, safe_image]})
  violations := deny with input as candidate
  some violation in violations
  startswith(violation, "P008:")
}

test_storage_for_each_service if {
  every service, target in {"postgres": "/var/lib/postgresql/data", "redis": "/data", "rails": "/app/storage", "sidekiq": "/app/storage", "prepare": "/app/storage"} {
    container := object.union(safe_container, {"name": service, "change": {"after": object.union(safe_container.change.after, {"volumes": []})}})
    candidate := object.union(safe_plan, {"resource_changes": [container, safe_image]})
    violations := deny with input as candidate
    sprintf("P008: %s requiere volumen nombrado en %s", [container.address, target]) in violations
  }
}

test_web_binding if {
  every ip in {"127.0.0.1", "0.0.0.0", "::", ""} {
    container := object.union(safe_container, {"name": "rails", "change": {"after": object.union(safe_container.change.after, {
      "name": "fixture-rails", "ports": [{"internal": 3000, "ip": ip, "protocol": "tcp"}],
      "volumes": [{"container_path": "/app/storage", "volume_name": "fixture-storage"}],
    })}})
    candidate := object.union(safe_plan, {"resource_changes": [container, safe_image]})
    violations := deny with input as candidate
    (count(violations) == 0) == (ip == "127.0.0.1")
  }
}

test_reject_wrong_input if {
  every document in [{}, {"format_version": "2.0", "resource_changes": []}, {"resource_changes": []}] {
    violations := deny with input as document
    "P001: se requiere JSON de un plan Terraform formato 1.x" in violations
  }
}

test_reject_empty_plan if {
  violations := deny with input as {"format_version": "1.2", "resource_changes": []}
  "P002: el plan debe contener contenedores Docker gestionados" in violations
}

test_ignore_deleted_resource if {
  removed := object.union(safe_container, {"address": "docker_container.removed", "change": {"actions": ["delete"], "after": null}})
  candidate := object.union(safe_plan, {"resource_changes": [safe_container, safe_image, removed]})
  violations := deny with input as candidate
  count(violations) == 0
}
