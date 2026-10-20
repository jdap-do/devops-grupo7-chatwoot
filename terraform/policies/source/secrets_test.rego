package main

import rego.v1

test_accept_external_sensitive_variables if {
  config := parse_config("hcl2", `
    variable "postgres_password" {
      type = string
      sensitive = true
    }
    variable "redis_password" {
      type = string
      sensitive = true
    }
    module "persistence" {
      source = "./modules/persistence"
      postgres_password = var.postgres_password
    }
    resource "docker_container" "postgres" {
      env = ["POSTGRES_PASSWORD=${var.postgres_password}"]
    }
    output "postgres_host" { value = module.persistence.postgres_host }
  `)
  violations := deny with input as config
  count(violations) == 0
}

test_reject_insecure_hcl if {
  cases := {
    "password_default": {"hcl": `variable "postgres_password" { default = "NOT_A_REAL_SECRET" }`, "code": "S001:"},
    "empty_password_default": {"hcl": `variable "redis_password" { default = "" }`, "code": "S001:"},
    "not_sensitive": {"hcl": `variable "redis_password" { type = string }`, "code": "S002:"},
    "secret_output": {"hcl": `output "postgres_password" { value = var.postgres_password }`, "code": "S003:"},
    "renamed_output": {"hcl": `output "connection" { value = "redis://:${var.redis_password}@redis:6379" }`, "code": "S003:"},
    "literal_module_password": {"hcl": `module "persistence" { postgres_password = "NOT_A_REAL_SECRET" }`, "code": "S004:"},
    "literal_local_password": {"hcl": `locals { postgres_password = "NOT_A_REAL_SECRET" }`, "code": "S004:"},
    "literal_env_password": {"hcl": `resource "docker_container" "postgres" { env = ["POSTGRES_PASSWORD=NOT_A_REAL_SECRET"] }`, "code": "S005:"},
    "literal_env_key": {"hcl": `resource "docker_container" "rails" { env = ["SECRET_KEY_BASE=NOT_A_REAL_SECRET"] }`, "code": "S005:"},
    "partial_secret_interpolation": {"hcl": `resource "docker_container" "redis" { env = ["REDIS_PASSWORD=prefix-${var.redis_password}"] }`, "code": "S005:"},
    "token_default": {"hcl": `variable "api_token" { default = "NOT_A_REAL_SECRET" }`, "code": "S001:"},
  }
  every _, case in cases {
    config := parse_config("hcl2", case.hcl)
    violations := deny with input as config
    some violation in violations
    startswith(violation, case.code)
  }
}

test_no_secret_in_diagnostics if {
  config := parse_config("hcl2", `resource "docker_container" "redis" { env = ["REDIS_PASSWORD=NOT_A_REAL_SECRET"] }`)
  violations := deny with input as config
  count(violations) > 0
  every violation in violations { not contains(violation, "NOT_A_REAL_SECRET") }
}

test_accept_nonsecret_defaults if {
  config := parse_config("hcl2", `
    variable "postgres_image" { default = "example.invalid/image@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
    locals { postgres_database = "chatwoot_production" }
    resource "docker_container" "postgres" { env = ["POSTGRES_DB=chatwoot_production"] }
  `)
  violations := deny with input as config
  count(violations) == 0
}
