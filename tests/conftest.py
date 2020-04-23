from hypothesis import HealthCheck, settings

settings.register_profile(
    "slow",
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
settings.load_profile("slow")
