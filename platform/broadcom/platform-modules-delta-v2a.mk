# Delta AG9032V2A platform module for the staged Trixie migration.
#
# Do not include platform-modules-delta.mk until every Delta child package is
# ported.  This declaration intentionally exposes only the V2A package.

DELTA_AG9032V2A_PLATFORM_MODULE_VERSION = 1.1
export DELTA_AG9032V2A_PLATFORM_MODULE_VERSION

DELTA_AG9032V2A_PLATFORM_MODULE = platform-modules-ag9032v2a_$(DELTA_AG9032V2A_PLATFORM_MODULE_VERSION)_amd64.deb
$(DELTA_AG9032V2A_PLATFORM_MODULE)_SRC_PATH = $(PLATFORM_PATH)/sonic-platform-modules-delta
$(DELTA_AG9032V2A_PLATFORM_MODULE)_DEPENDS += $(LINUX_HEADERS) $(LINUX_HEADERS_COMMON)
$(DELTA_AG9032V2A_PLATFORM_MODULE)_PLATFORM = x86_64-delta_ag9032v2a-r0

SONIC_DPKG_DEBS += $(DELTA_AG9032V2A_PLATFORM_MODULE)
