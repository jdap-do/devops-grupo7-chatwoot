package main

import rego.v1

secret_name(name) if {
  regex.match(`(?i)(password|secret_key_base|(^|_)token($|_)|(^|_)credentials?($|_))`, name)
}

external_variable(value) if {
  is_string(value)
  regex.match(`^\$\{var\.[a-zA-Z0-9_]+\}$`, value)
}

deny contains sprintf("S001: variable %s no debe tener default de credenciales", [name]) if {
  some name, blocks in input.variable
  secret_name(name)
  some block in blocks
  "default" in object.keys(block)
}

deny contains sprintf("S002: variable %s debe declarar sensitive = true", [name]) if {
  some name, blocks in input.variable
  secret_name(name)
  some block in blocks
  object.get(block, "sensitive", false) != true
}

deny contains sprintf("S003: output %s no puede exponer credenciales", [name]) if {
  some name in object.keys(input.output)
  secret_name(name)
}

deny contains sprintf("S003: output %s no puede referenciar variables de credenciales", [name]) if {
  some name, blocks in input.output
  walk(blocks, [_, value])
  is_string(value)
  regex.match(`(?i)var\.[a-z0-9_]*(password|secret_key_base|token|credential)`, value)
}

# Parámetros de módulos/recursos y locals con nombres de credenciales solo pueden
# reenviar una variable externa. No se imprimen sus valores.
deny contains sprintf("S004: %s debe recibir credenciales desde una variable externa", [key]) if {
  walk(input, [path, value])
  count(path) > 1
  path[0] in {"module", "resource", "locals", "provider"}
  key := path[count(path)-1]
  is_string(key)
  secret_name(key)
  not external_variable(value)
}

deny contains "S005: variables de entorno de credenciales deben referenciar directamente var.*" if {
  walk(input.resource, [path, value])
  count(path) > 0
  path[count(path)-1] == "env"
  some entry in value
  is_string(entry)
  key := split(entry, "=")[0]
  secret_name(key)
  not regex.match(`^[A-Z0-9_]+=\$\{var\.[a-zA-Z0-9_]+\}$`, entry)
}
