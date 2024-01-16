# ------------------------------------------------------------------------------
#  Copyright 2022 Upstream Data Inc                                            -
#                                                                              -
#  Licensed under the Apache License, Version 2.0 (the "License");             -
#  you may not use this file except in compliance with the License.            -
#  You may obtain a copy of the License at                                     -
#                                                                              -
#      http://www.apache.org/licenses/LICENSE-2.0                              -
#                                                                              -
#  Unless required by applicable law or agreed to in writing, software         -
#  distributed under the License is distributed on an "AS IS" BASIS,           -
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.    -
#  See the License for the specific language governing permissions and         -
#  limitations under the License.                                              -
# ------------------------------------------------------------------------------

from typing import List, Optional

from pyasic.config import MinerConfig
from pyasic.data import Fan, HashBoard
from pyasic.data.error_codes import MinerErrorData, X19Error
from pyasic.errors import APIError
from pyasic.logger import logger
from pyasic.miners.base import (
    BaseMiner,
    DataFunction,
    DataLocations,
    DataOptions,
    WebAPICommand,
)
from pyasic.web.epic import ePICWebAPI

EPIC_DATA_LOC = DataLocations(
    **{
        str(DataOptions.MAC): DataFunction(
            "_get_mac", [WebAPICommand("web_network", "network")]
        ),
        str(DataOptions.API_VERSION): DataFunction("_get_api_ver"),
        str(DataOptions.FW_VERSION): DataFunction(
            "_get_fw_ver", [WebAPICommand("web_summary", "summary")]
        ),
        str(DataOptions.HOSTNAME): DataFunction(
            "_get_hostname", [WebAPICommand("web_summary", "summary")]
        ),
        str(DataOptions.HASHRATE): DataFunction(
            "_get_hashrate", [WebAPICommand("web_summary", "summary")]
        ),
        str(DataOptions.EXPECTED_HASHRATE): DataFunction(
            "_get_expected_hashrate", [WebAPICommand("web_summary", "summary")]
        ),
        str(DataOptions.HASHBOARDS): DataFunction(
            "_get_hashboards",
            [
                WebAPICommand("web_summary", "summary"),
                WebAPICommand("web_hashrate", "hashrate"),
            ],
        ),
        str(DataOptions.ENVIRONMENT_TEMP): DataFunction("_get_env_temp"),
        str(DataOptions.WATTAGE): DataFunction(
            "_get_wattage", [WebAPICommand("web_summary", "summary")]
        ),
        str(DataOptions.WATTAGE_LIMIT): DataFunction("_get_wattage_limit"),
        str(DataOptions.FANS): DataFunction(
            "_get_fans", [WebAPICommand("web_summary", "summary")]
        ),
        str(DataOptions.FAN_PSU): DataFunction("_get_fan_psu"),
        str(DataOptions.ERRORS): DataFunction(
            "_get_errors", [WebAPICommand("web_summary", "summary")]
        ),
        str(DataOptions.FAULT_LIGHT): DataFunction(
            "_get_fault_light", [WebAPICommand("web_summary", "summary")]
        ),
        str(DataOptions.IS_MINING): DataFunction("_is_mining"),
        str(DataOptions.UPTIME): DataFunction(
            "_get_uptime", [WebAPICommand("web_summary", "summary")]
        ),
        str(DataOptions.CONFIG): DataFunction("get_config"),
    }
)


class ePIC(BaseMiner):
    def __init__(self, ip: str, api_ver: str = "0.0.0") -> None:
        super().__init__(ip, api_ver)
        # interfaces
        self.web = ePICWebAPI(ip)

        # static data
        self.api_type = "ePIC"
        self.fw_str = "ePIC"
        # data gathering locations
        self.data_locations = EPIC_DATA_LOC

    async def get_config(self) -> MinerConfig:
        summary = None
        try:
            summary = await self.web.summary()
        except APIError as e:
            logger.warning(e)
        except LookupError:
            pass

        if summary is not None:
            cfg = MinerConfig.from_epic(summary)
        else:
            cfg = MinerConfig()

        self.config = cfg
        return self.config

    async def restart_backend(self) -> bool:
        data = await self.web.restart_epic()
        if data:
            try:
                return data["success"]
            except KeyError:
                pass
        return False

    async def stop_mining(self) -> bool:
        data = await self.web.stop_mining()
        if data:
            try:
                return data["success"]
            except KeyError:
                pass
        return False

    async def resume_mining(self) -> bool:
        data = await self.web.resume_mining()
        if data:
            try:
                return data["success"]
            except KeyError:
                pass
        return False

    async def reboot(self) -> bool:
        data = await self.web.reboot()
        if data:
            try:
                return data["success"]
            except KeyError:
                pass
        return False

    async def _get_mac(self, web_network: dict = None) -> str:
        if web_network is None:
            try:
                web_network = await self.web.network()
            except APIError:
                pass

        if web_network is not None:
            try:
                for network in web_network:
                    mac = web_network[network]["mac_address"]
                    return mac
            except KeyError:
                pass

    async def _get_hostname(self, web_summary: dict = None) -> str:
        if web_summary is None:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        if web_summary is not None:
            try:
                hostname = web_summary["Hostname"]
                return hostname
            except KeyError:
                pass

    async def _get_wattage(self, web_summary: dict = None) -> Optional[int]:
        if web_summary is None:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        if web_summary is not None:
            try:
                wattage = web_summary["Power Supply Stats"]["Input Power"]
                wattage = round(wattage)
                return wattage
            except KeyError:
                pass

    async def _get_hashrate(self, web_summary: dict = None) -> Optional[float]:
        if web_summary is None:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        if web_summary is not None:
            try:
                hashrate = 0
                if web_summary["HBs"] is not None:
                    for hb in web_summary["HBs"]:
                        hashrate += hb["Hashrate"][0]
                    return round(float(float(hashrate / 1000000)), 2)
            except (LookupError, ValueError, TypeError):
                pass

    async def _get_expected_hashrate(self, web_summary: dict = None) -> Optional[float]:
        if web_summary is None:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        if web_summary is not None:
            try:
                hashrate = 0
                if web_summary.get("HBs") is not None:
                    for hb in web_summary["HBs"]:
                        if hb["Hashrate"][1] == 0:
                            ideal = 1.0
                        else:
                            ideal = hb["Hashrate"][1] / 100

                        hashrate += hb["Hashrate"][0] / ideal
                    return round(float(float(hashrate / 1000000)), 2)
            except (LookupError, ValueError, TypeError):
                pass

    async def _get_fw_ver(self, web_summary: dict = None) -> Optional[str]:
        if web_summary is None:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        if web_summary is not None:
            try:
                fw_ver = web_summary["Software"]
                fw_ver = fw_ver.split(" ")[1].replace("v", "")
                return fw_ver
            except KeyError:
                pass

    async def _get_fans(self, web_summary: dict = None) -> List[Fan]:
        if web_summary is None:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        fans = []

        if web_summary is not None:
            for fan in web_summary["Fans Rpm"]:
                try:
                    fans.append(Fan(web_summary["Fans Rpm"][fan]))
                except (LookupError, ValueError, TypeError):
                    fans.append(Fan())
        return fans

    async def _get_hashboards(
        self, web_summary: dict = None, web_hashrate: dict = None
    ) -> List[HashBoard]:
        if web_summary is None:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        if web_hashrate is not None:
            try:
                web_hashrate = await self.web.hashrate()
            except APIError:
                pass
        hb_list = [
            HashBoard(slot=i, expected_chips=self.expected_chips)
            for i in range(self.expected_hashboards)
        ]

        if web_summary.get("HBs") is not None:
            for hb in web_summary["HBs"]:
                for hr in web_hashrate:
                    if hr["Index"] == hb["Index"]:
                        num_of_chips = len(hr["Data"])
                        hashrate = hb["Hashrate"][0]
                        # Update the Hashboard object
                        hb_list[hr["Index"]].expected_chips = num_of_chips
                        hb_list[hr["Index"]].missing = False
                        hb_list[hr["Index"]].hashrate = round(hashrate / 1000000, 2)
                        hb_list[hr["Index"]].chips = num_of_chips
                        hb_list[hr["Index"]].temp = hb["Temperature"]
        return hb_list

    async def _is_mining(self, *args, **kwargs) -> Optional[bool]:
        return None

    async def _get_uptime(self, web_summary: dict = None) -> Optional[int]:
        if web_summary is None:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        if web_summary is not None:
            try:
                uptime = web_summary["Session"]["Uptime"]
                return uptime
            except KeyError:
                pass
        return None

    async def _get_fault_light(self, web_summary: dict = None) -> bool:
        if web_summary is None:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        if web_summary is not None:
            try:
                light = web_summary["Misc"]["Locate Miner State"]
                return light
            except KeyError:
                pass
        return False

    async def _get_errors(self, web_summary: dict = None) -> List[MinerErrorData]:
        if not web_summary:
            try:
                web_summary = await self.web.summary()
            except APIError:
                pass

        errors = []
        if web_summary is not None:
            try:
                error = web_summary["Status"]["Last Error"]
                if error is not None:
                    errors.append(X19Error(str(error)))
                return errors
            except KeyError:
                pass
        return errors

    async def fault_light_off(self) -> bool:
        return False

    async def fault_light_on(self) -> bool:
        return False

    async def _get_api_ver(self, *args, **kwargs) -> Optional[str]:
        pass

    async def _get_env_temp(self, *args, **kwargs) -> Optional[float]:
        pass

    async def _get_fan_psu(self, *args, **kwargs) -> Optional[int]:
        pass

    async def _get_wattage_limit(self, *args, **kwargs) -> Optional[int]:
        pass

    async def send_config(self, config: MinerConfig, user_suffix: str = None) -> None:
        pass

    async def set_power_limit(self, wattage: int) -> bool:
        return False
