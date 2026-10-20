package main

import rego.v1

# Entrada: terraform show -json <plan>. Nunca incluir valores sensibles en mensajes.
containers contains resource if {
  some resource in input.resource_changes
  resource.mode == "managed"
  resource.type == "docker_container"
  resource.change.after != null
}

images contains resource if {
  some resource in input.resource_changes
  resource.mode == "managed"
  resource.type == "docker_image"
  resource.change.after != null
}

valid_plan if {
  regex.match(`^1\.`, input.format_version)
  is_array(input.resource_changes)
}

deny contains "P001: se requiere JSON de un plan Terraform formato 1.x" if {
  not valid_plan
}

deny contains "P002: el plan debe contener contenedores Docker gestionados" if {
  count(containers) == 0
}

deny contains sprintf("P003: %s no puede usar modo privilegiado", [r.address]) if {
  some r in containers
  r.change.after.privileged == true
}

deny contains sprintf("P004: %s no puede compartir namespaces del anfitrión", [r.address]) if {
  some r in containers
  some field in {"network_mode", "pid_mode", "ipc_mode"}
  r.change.after[field] == "host"
}

deny contains sprintf("P005: %s no puede publicar automáticamente todos los puertos", [r.address]) if {
  some r in containers
  r.change.after.publish_all_ports == true
}

is_rails(r) if { r.name == "rails" }
is_rails(r) if { endswith(r.change.after.name, "-rails") }

allowed_web_port(r, port) if {
  is_rails(r)
  port.internal == 3000
  port.ip == "127.0.0.1"
  object.get(port, "protocol", "tcp") == "tcp"
}

deny contains sprintf("P006: %s solo puede publicar Rails:3000 en 127.0.0.1/TCP", [r.address]) if {
  some r in containers
  some port in r.change.after.ports
  not allowed_web_port(r, port)
}

runtime_socket(path) if {
  normalized := lower(replace(path, `\`, "/"))
  regex.match(`(^|/)(docker\.sock|docker_engine|dockerdesktoplinuxengine)$`, normalized)
}

runtime_socket(path) if {
  trim_suffix(path, "/") in {"/var/run", "/run", ""}
}

deny contains sprintf("P007: %s no puede montar el socket Docker ni su directorio", [r.address]) if {
  some r in containers
  some mount in r.change.after.volumes
  mount.host_path != ""
  runtime_socket(mount.host_path)
}

deny contains sprintf("P007: %s no puede montar el socket Docker ni su directorio", [r.address]) if {
  some r in containers
  some mount in r.change.after.mounts
  mount.type == "bind"
  runtime_socket(mount.source)
}

storage_targets := {"postgres": "/var/lib/postgresql/data", "redis": "/data", "rails": "/app/storage", "sidekiq": "/app/storage", "prepare": "/app/storage"}

required_storage(r) := targets if {
  by_resource := {target | target := storage_targets[r.name]}
  by_name := {target | some role, target in storage_targets; endswith(r.change.after.name, sprintf("-%s", [role]))}
  targets := by_resource | by_name
}

named_volume(values, target) if {
  some mount in values.volumes
  mount.container_path == target
  is_string(mount.volume_name)
  mount.volume_name != ""
  object.get(mount, "host_path", "") in {"", null}
}

named_volume(values, target) if {
  some mount in values.mounts
  mount.target == target
  mount.type == "volume"
  is_string(mount.source)
  mount.source != ""
}

deny contains sprintf("P008: %s requiere volumen nombrado en %s", [r.address, target]) if {
  some r in containers
  some target in required_storage(r)
  not named_volume(r.change.after, target)
}

deny contains sprintf("P009: %s requiere una imagen fijada por digest SHA256", [r.address]) if {
  some r in images
  not digest_reference(object.get(r.change.after, "name", ""))
}

digest_reference(image) if {
  is_string(image)
  regex.match(`^.+@sha256:[a-f0-9]{64}$`, image)
}

fixed_container_image(image) if {
  is_string(image)
  regex.match(`^sha256:[a-f0-9]{64}$`, image)
}
fixed_container_image(image) if { digest_reference(image) }

# Las direcciones de configuración son relativas al módulo, incluso si el recurso
# del plan tiene índices count/for_each. Los módulos anidados se recorren con walk.
configuration_resource(r) := config if {
  walk(input.configuration.root_module, [path, node])
  is_object(node)
  some config in object.get(node, "resources", [])
  modules := [sprintf("module.%s", [path[i+1]]) | some i; path[i] == "module_calls"]
  address := concat(".", array.concat(modules, [config.address]))
  address == regex.replace(r.address, `\[[^\]]*\]`, "")
}

managed_image_reference(r) if {
  r.change.after_unknown.image == true
  config := configuration_resource(r)
  some reference in config.expressions.image.references
  regex.match(`^docker_image\.[a-zA-Z0-9_-]+\.image_id$`, reference)
}

deny contains sprintf("P010: %s requiere imagen inmutable o referencia a docker_image.image_id", [r.address]) if {
  some r in containers
  not fixed_container_image(object.get(r.change.after, "image", ""))
  not managed_image_reference(r)
}

# Si un dato de seguridad aún es desconocido, no dar un resultado verde.
deny contains sprintf("P011: %s tiene %s desconocido; resolver antes de aplicar", [r.address, field]) if {
  some r in containers
  some field in {"privileged", "publish_all_ports", "ports", "network_mode", "pid_mode", "ipc_mode", "volumes", "mounts"}
  unknown := object.get(object.get(r.change, "after_unknown", {}), field, false)
  walk(unknown, [_, true])
}

deny contains sprintf("P011: %s tiene nombre de imagen desconocido", [r.address]) if {
  some r in images
  r.change.after_unknown.name == true
}
