tflint {
  required_version = "= 0.58.1"
}

config {
  # --recursive revisa cada directorio una vez, sin volver a recorrer sus módulos.
  call_module_type = "none"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

rule "terraform_documented_variables" {
  enabled = true
}

rule "terraform_documented_outputs" {
  enabled = true
}

rule "terraform_typed_variables" {
  enabled = true
}

rule "terraform_naming_convention" {
  enabled = true
  format  = "snake_case"
}
