"""Unit tests for bring-api."""

import asyncio
import enum

import aiohttp
from dotenv import load_dotenv
import pytest

from bring_api.bring import Bring
from bring_api.const import BRING_SUPPORTED_LOCALES
from bring_api.exceptions import (
    BringAuthException,
    BringEMailInvalidException,
    BringParseException,
    BringRequestException,
    BringUserUnknownException,
)
from bring_api.types import BringItem, BringItemOperation, BringNotificationType

from .conftest import (
    BRING_GET_ALL_ITEM_DETAILS_RESPONSE,
    BRING_GET_LIST_RESPONSE,
    BRING_LOAD_LISTS_RESPONSE,
    BRING_LOGIN_RESPONSE,
    BRING_USER_ACCOUNT_RESPONSE,
    UUID,
)

load_dotenv()


class TestDoesUserExist:
    """Tests for does_user_exist method."""

    async def test_mail_invalid(self, mocked, bring):
        """Test does_user_exist for invalid e-mail."""
        mocked.get("https://api.getbring.com/rest/bringusers?email=EMAIL", status=400)
        with pytest.raises(BringEMailInvalidException):
            await bring.does_user_exist("EMAIL")

    async def test_unknown_user(self, mocked, bring):
        """Test does_user_exist for unknown user."""
        mocked.get("https://api.getbring.com/rest/bringusers?email=EMAIL", status=404)
        with pytest.raises(BringUserUnknownException):
            await bring.does_user_exist("EMAIL")

    async def test_user_exist_with_parameter(self, mocked, bring):
        """Test does_user_exist for known user."""
        mocked.get("https://api.getbring.com/rest/bringusers?email=EMAIL", status=200)
        assert await bring.does_user_exist("EMAIL") is True

    async def test_user_exist_without_parameter(self, mocked, bring):
        """Test does_user_exist for known user."""
        mocked.get(
            "https://api.getbring.com/rest/bringusers?email=EMAIL",
            status=200,
        )
        assert await bring.does_user_exist() is True

    @pytest.mark.parametrize(
        ("exception", "expected"),
        [
            (asyncio.TimeoutError, BringRequestException),
            (aiohttp.ClientError, BringEMailInvalidException),
        ],
    )
    async def test_request_exception(self, mocked, bring, exception, expected):
        """Test request exceptions."""

        mocked.get(
            "https://api.getbring.com/rest/bringusers?email=EMAIL",
            exception=exception,
        )

        with pytest.raises(expected):
            await bring.does_user_exist("EMAIL")


class TestLogin:
    """Tests for login method."""

    async def test_mail_invalid(self, mocked, bring):
        """Test login with invalid e-mail."""
        mocked.post(
            "https://api.getbring.com/rest/v2/bringauth",
            status=400,
        )
        expected = "Login failed due to bad request, please check your email."
        with pytest.raises(BringAuthException, match=expected):
            await bring.login()

    async def test_unauthorized(self, mocked, bring):
        """Test login with unauthorized user."""
        mocked.post(
            "https://api.getbring.com/rest/v2/bringauth",
            status=401,
            payload={"message": ""},
        )
        expected = "Login failed due to authorization failure, please check your email and password."
        with pytest.raises(BringAuthException, match=expected):
            await bring.login()

    @pytest.mark.parametrize("status", [200, 401])
    async def test_parse_exception(self, mocked, bring, status):
        """Test parse exceptions."""
        mocked.post(
            "https://api.getbring.com/rest/v2/bringauth",
            status=status,
            body="not json",
            content_type="application/json",
        )

        with pytest.raises(BringParseException):
            await bring.login()

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exceptions(self, mocked, bring, exception):
        """Test exceptions."""
        mocked.post("https://api.getbring.com/rest/v2/bringauth", exception=exception)
        with pytest.raises(BringRequestException):
            await bring.login()

    async def test_login(self, mocked, bring, monkeypatch):
        """Test login with valid user."""

        mocked.post(
            "https://api.getbring.com/rest/v2/bringauth",
            status=200,
            payload=BRING_LOGIN_RESPONSE,
        )

        async def mocked_get_user_account(*args, **kwargs):
            """Mock get_user_account."""
            return {"userLocale": {"language": "de", "country": "DE"}}

        async def mocked__load_user_list_settings(*args, **kwargs):
            """Mock __load_user_list_settings."""
            return {UUID: {"listArticleLanguage": "de-DE"}}

        async def mocked__load_article_translations(*args, **kwargs):
            """Mock __load_article_translations."""
            return {}

        monkeypatch.setattr(Bring, "get_user_account", mocked_get_user_account)
        monkeypatch.setattr(
            Bring, "_Bring__load_user_list_settings", mocked__load_user_list_settings
        )
        monkeypatch.setattr(
            Bring,
            "_Bring__load_article_translations",
            mocked__load_article_translations,
        )

        data = await bring.login()
        assert data == BRING_LOGIN_RESPONSE
        assert bring.headers["Authorization"] == "Bearer ACCESS_TOKEN"
        assert bring.headers["X-BRING-COUNTRY"] == "DE"
        assert bring.uuid == UUID
        assert bring.public_uuid == UUID
        assert bring.user_locale == "de-DE"


class TestLoadLists:
    """Tests for load_lists method."""

    async def test_load_lists(self, bring, mocked, monkeypatch):
        """Test load_lists."""

        mocked.get(
            f"https://api.getbring.com/rest/bringusers/{UUID}/lists",
            status=200,
            payload=BRING_LOAD_LISTS_RESPONSE,
        )
        monkeypatch.setattr(bring, "uuid", UUID)

        lists = await bring.load_lists()

        assert lists == BRING_LOAD_LISTS_RESPONSE

    async def test_parse_exception(self, mocked, bring, monkeypatch):
        """Test parse exceptions."""
        mocked.get(
            f"https://api.getbring.com/rest/bringusers/{UUID}/lists",
            status=200,
            body="not json",
            content_type="application/json",
        )
        monkeypatch.setattr(bring, "uuid", UUID)

        with pytest.raises(BringParseException):
            await bring.load_lists()

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exception(self, mocked, bring, exception, monkeypatch):
        """Test request exceptions."""
        mocked.get(
            f"https://api.getbring.com/rest/bringusers/{UUID}/lists",
            exception=exception,
        )
        monkeypatch.setattr(bring, "uuid", UUID)

        with pytest.raises(BringRequestException):
            await bring.load_lists()


class TestNotifications:
    """Tests for notification method."""

    @pytest.mark.parametrize(
        ("notification_type", "item_name"),
        [
            (BringNotificationType.GOING_SHOPPING, ""),
            (BringNotificationType.CHANGED_LIST, ""),
            (BringNotificationType.SHOPPING_DONE, ""),
            (BringNotificationType.URGENT_MESSAGE, "WITH_ITEM_NAME"),
        ],
    )
    async def test_notify(
        self,
        bring,
        notification_type: BringNotificationType,
        item_name: str,
        mocked,
    ):
        """Test GOING_SHOPPING notification."""

        mocked.post(
            f"https://api.getbring.com/rest/v2/bringnotifications/lists/{UUID}",
            status=200,
        )
        resp = await bring.notify(UUID, notification_type, item_name)
        assert resp.status == 200

    async def test_notify_urgent_message_item_name_missing(self, bring, mocked):
        """Test URGENT_MESSAGE notification."""
        mocked.post(
            f"https://api.getbring.com/rest/v2/bringnotifications/lists/{UUID}",
            status=200,
        )
        with pytest.raises(
            ValueError,
            match="notificationType is URGENT_MESSAGE but argument itemName missing.",
        ):
            await bring.notify(UUID, BringNotificationType.URGENT_MESSAGE, "")

    async def test_notify_notification_type_raise_attribute_error(self, bring, mocked):
        """Test URGENT_MESSAGE notification."""

        with pytest.raises(
            AttributeError,
        ):
            await bring.notify(UUID, "STRING", "")

    async def test_notify_notification_type_raise_type_error(self, bring, mocked):
        """Test URGENT_MESSAGE notification."""

        class WrongEnum(enum.Enum):
            """Test Enum."""

            UNKNOWN = "UNKNOWN"

        with pytest.raises(
            TypeError,
            match="notificationType WrongEnum.UNKNOWN not supported,"
            "must be of type BringNotificationType.",
        ):
            await bring.notify(UUID, WrongEnum.UNKNOWN, "")

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exception(self, mocked, bring, exception):
        """Test request exceptions."""

        mocked.post(
            f"https://api.getbring.com/rest/v2/bringnotifications/lists/{UUID}",
            exception=exception,
        )

        with pytest.raises(BringRequestException):
            await bring.notify(UUID, BringNotificationType.GOING_SHOPPING)


class TestGetList:
    """Tests for get_list method."""

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exception(self, mocked, bring, exception):
        """Test request exceptions."""

        mocked.get(
            f"https://api.getbring.com/rest/v2/bringlists/{UUID}",
            exception=exception,
        )

        with pytest.raises(BringRequestException):
            await bring.get_list(UUID)

    async def test_parse_exception(self, mocked, bring, monkeypatch):
        """Test parse exceptions."""
        mocked.get(
            f"https://api.getbring.com/rest/v2/bringlists/{UUID}",
            status=200,
            body="not json",
            content_type="application/json",
        )
        monkeypatch.setattr(bring, "uuid", UUID)

        with pytest.raises(BringParseException):
            await bring.get_list(UUID)

    async def test_get_list(self, mocked, bring, monkeypatch):
        """Test get list."""
        mocked.get(
            f"https://api.getbring.com/rest/v2/bringlists/{UUID}",
            status=200,
            payload=BRING_GET_LIST_RESPONSE,
        )

        def mocked_locale(*args, **kwargs) -> str:
            return "de-CH"

        monkeypatch.setattr(Bring, "_Bring__locale", mocked_locale)

        def mocked_translate(bring: Bring, item_id: str, *args, **kwargs) -> str:
            return item_id

        monkeypatch.setattr(Bring, "_Bring__translate", mocked_translate)
        monkeypatch.setattr(bring, "uuid", UUID)

        data = await bring.get_list(UUID)
        assert data == BRING_GET_LIST_RESPONSE["items"]


class TestGetAllItemDetails:
    """Test for get_all_item_details method."""

    async def test_get_all_item_details(self, mocked, bring):
        """Test get_all_item_details."""
        mocked.get(
            f"https://api.getbring.com/rest/bringlists/{UUID}/details",
            status=200,
            payload=BRING_GET_ALL_ITEM_DETAILS_RESPONSE,
        )

        data = await bring.get_all_item_details(UUID)
        assert data == BRING_GET_ALL_ITEM_DETAILS_RESPONSE

    async def test_list_not_found(self, mocked, bring):
        """Test get_all_item_details."""
        mocked.get(
            f"https://api.getbring.com/rest/bringlists/{UUID}/details",
            status=404,
            reason=f"List with uuid '{UUID}' not found",
        )

        with pytest.raises(BringRequestException):
            await bring.get_all_item_details(UUID)

    async def test_parse_exception(self, mocked, bring):
        """Test parse exceptions."""
        mocked.get(
            f"https://api.getbring.com/rest/bringlists/{UUID}/details",
            status=200,
            body="not json",
            content_type="application/json",
        )

        with pytest.raises(BringParseException):
            await bring.get_all_item_details(UUID)

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exception(self, mocked, bring, exception):
        """Test request exceptions."""

        mocked.get(
            f"https://api.getbring.com/rest/bringlists/{UUID}/details",
            exception=exception,
        )

        with pytest.raises(BringRequestException):
            await bring.get_all_item_details(UUID)


async def mocked_batch_update_list(
    bring: Bring,
    list_uuid: str,
    items: BringItem,
    operation: BringItemOperation,
):
    """Mock batch_update_list."""
    return (list_uuid, items, operation)


class TestSaveItem:
    """Test for save_item method."""

    @pytest.mark.parametrize(
        ("item_name", "specification", "item_uuid"),
        [
            ("item name", "", None),
            ("item name", "specification", None),
            ("item name", "", UUID),
        ],
    )
    async def test_save_item(
        self, bring, monkeypatch, item_name, specification, item_uuid
    ):
        """Test save_item."""

        monkeypatch.setattr(Bring, "batch_update_list", mocked_batch_update_list)

        list_uuid, items, operation = await bring.save_item(
            UUID, item_name, specification, item_uuid
        )
        assert list_uuid == UUID
        expected = {"itemId": item_name, "spec": specification, "uuid": item_uuid}
        assert expected == items
        assert operation == BringItemOperation.ADD

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exception(self, mocked, bring, exception):
        """Test request exceptions."""

        mocked.put(
            f"https://api.getbring.com/rest/v2/bringlists/{UUID}/items",
            exception=exception,
        )

        with pytest.raises(BringRequestException) as exc:
            await bring.save_item(UUID, "item_name", "specification")
        assert (
            exc.value.args[0]
            == f"Saving item item_name (specification) to list {UUID} "
            "failed due to request exception."
        )


class TestUpdateItem:
    """Test for save_item method."""

    @pytest.mark.parametrize(
        ("item_name", "specification", "item_uuid"),
        [
            ("item name", "", None),
            ("item name", "specification", None),
            ("item name", "", UUID),
        ],
    )
    async def test_update_item(
        self, bring, monkeypatch, item_name, specification, item_uuid
    ):
        """Test save_item."""

        monkeypatch.setattr(Bring, "batch_update_list", mocked_batch_update_list)

        list_uuid, items, operation = await bring.update_item(
            UUID, item_name, specification, item_uuid
        )
        assert list_uuid == UUID
        expected = {"itemId": item_name, "spec": specification, "uuid": item_uuid}
        assert expected == items
        assert operation == BringItemOperation.ADD

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exception(self, mocked, bring, exception):
        """Test request exceptions."""

        mocked.put(
            f"https://api.getbring.com/rest/v2/bringlists/{UUID}/items",
            exception=exception,
        )

        with pytest.raises(BringRequestException) as exc:
            await bring.update_item(UUID, "item_name", "specification")
        assert (
            exc.value.args[0]
            == f"Updating item item_name (specification) in list {UUID} "
            "failed due to request exception."
        )


class TestRemoveItem:
    """Test for save_item method."""

    @pytest.mark.parametrize(
        ("item_name", "item_uuid"),
        [
            ("item name", None),
            ("item name", UUID),
        ],
    )
    async def test_remove_item(self, bring, monkeypatch, item_name, item_uuid):
        """Test save_item."""

        monkeypatch.setattr(Bring, "batch_update_list", mocked_batch_update_list)

        list_uuid, items, operation = await bring.remove_item(
            UUID, item_name, item_uuid
        )
        assert list_uuid == UUID
        expected = {"itemId": item_name, "spec": "", "uuid": item_uuid}
        assert expected == items
        assert operation == BringItemOperation.REMOVE

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exception(self, mocked, bring, exception):
        """Test request exceptions."""

        mocked.put(
            f"https://api.getbring.com/rest/v2/bringlists/{UUID}/items",
            exception=exception,
        )

        with pytest.raises(BringRequestException) as exc:
            await bring.remove_item(UUID, "item_name")
        assert (
            exc.value.args[0] == f"Removing item item_name from list {UUID} "
            "failed due to request exception."
        )


class TestCompleteItem:
    """Test for save_item method."""

    @pytest.mark.parametrize(
        ("item_name", "specification", "item_uuid"),
        [
            ("item name", "", None),
            ("item name", "specification", None),
            ("item name", "", UUID),
        ],
    )
    async def test_complete_item(
        self, bring, monkeypatch, item_name, specification, item_uuid
    ):
        """Test save_item."""

        monkeypatch.setattr(Bring, "batch_update_list", mocked_batch_update_list)

        list_uuid, items, operation = await bring.complete_item(
            UUID, item_name, specification, item_uuid
        )
        assert list_uuid == UUID
        expected = {"itemId": item_name, "spec": specification, "uuid": item_uuid}
        assert expected == items
        assert operation == BringItemOperation.COMPLETE

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exception(self, mocked, bring, exception):
        """Test request exceptions."""

        mocked.put(
            f"https://api.getbring.com/rest/v2/bringlists/{UUID}/items",
            exception=exception,
        )

        with pytest.raises(BringRequestException) as exc:
            await bring.complete_item(UUID, "item_name")
        assert (
            exc.value.args[0] == f"Completing item item_name from list {UUID} "
            "failed due to request exception."
        )


class TestLoadArticleTranslations:
    """Test loading of article translation tables."""

    def mocked__load_article_translations_from_file(self, locale):
        """Mock and raise for fallback to ressource download."""
        raise OSError()

    def test_load_file(self, bring, mocked):
        """Test loading json from file."""

        dictionary = bring._Bring__load_article_translations_from_file("de-CH")

        assert "Pouletbrüstli" in dictionary
        assert dictionary["Pouletbrüstli"] == "Pouletbrüstli"
        assert len(dictionary) == 444

    async def test_load_from_list_article_language(self, bring, monkeypatch):
        """Test loading json from listArticleLanguage."""

        monkeypatch.setattr(
            bring, "user_list_settings", {UUID: {"listArticleLanguage": "de-DE"}}
        )

        dictionaries = await bring._Bring__load_article_translations()

        assert "de-DE" in dictionaries
        assert dictionaries["de-DE"]["Pouletbrüstli"] == "Hähnchenbrust"
        assert len(dictionaries["de-DE"]) == 444

    async def test_load_from_user_locale(self, bring, monkeypatch):
        """Test loading json from user_locale."""

        monkeypatch.setattr(bring, "user_locale", "de-DE")

        dictionaries = await bring._Bring__load_article_translations()

        assert "de-DE" in dictionaries
        assert dictionaries["de-DE"]["Pouletbrüstli"] == "Hähnchenbrust"
        assert len(dictionaries["de-DE"]) == 444

    @pytest.mark.parametrize(
        ("test_locale", "expected_locale"),
        [
            ("de-XX", "de-DE"),
            ("en-XX", "en-US"),
            ("es-XX", "es-ES"),
            ("de-DE", "de-DE"),
            ("en-GB", "en-GB"),
        ],
    )
    async def test_map_user_language_to_locale(
        self, bring, test_locale, expected_locale
    ):
        """Test mapping invalid user_locale to valid locale."""

        user_locale = {"language": test_locale[0:2], "country": test_locale[3:5]}
        locale = bring.map_user_language_to_locale(user_locale)

        assert expected_locale == locale

    async def test_load_all_locales(self, bring, monkeypatch):
        """Test loading all locales."""

        user_list_settings = {
            k: {"listArticleLanguage": v} for k, v in enumerate(BRING_SUPPORTED_LOCALES)
        }

        monkeypatch.setattr(bring, "user_list_settings", user_list_settings)
        dictionaries = await bring._Bring__load_article_translations()

        assert len(dictionaries) == 19  # de-CH is skipped

    async def test_load_fallback_to_download(self, bring, mocked, monkeypatch):
        """Test loading json and fallback to download from web."""
        mocked.get(
            "https://web.getbring.com/locale/articles.de-DE.json",
            payload={"test": "test"},
            status=200,
        )

        monkeypatch.setattr(bring, "user_locale", "de-DE")

        monkeypatch.setattr(
            Bring,
            "_Bring__load_article_translations_from_file",
            self.mocked__load_article_translations_from_file,
        )

        dictionaries = await bring._Bring__load_article_translations()

        assert dictionaries["de-DE"] == {"test": "test"}

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exceptions(self, bring, mocked, monkeypatch, exception):
        """Test loading json and fallback to download from web."""
        mocked.get(
            "https://web.getbring.com/locale/articles.de-DE.json", exception=exception
        )

        monkeypatch.setattr(bring, "user_locale", "de-DE")

        monkeypatch.setattr(
            Bring,
            "_Bring__load_article_translations_from_file",
            self.mocked__load_article_translations_from_file,
        )
        with pytest.raises(BringRequestException):
            await bring._Bring__load_article_translations()

    async def test_parse_exception(self, bring, mocked, monkeypatch):
        """Test loading json and fallback to download from web."""
        mocked.get(
            "https://web.getbring.com/locale/articles.de-DE.json",
            status=200,
            body="not json",
            content_type="application/json",
        )

        monkeypatch.setattr(bring, "user_locale", "de-DE")

        monkeypatch.setattr(
            Bring,
            "_Bring__load_article_translations_from_file",
            self.mocked__load_article_translations_from_file,
        )
        with pytest.raises(BringParseException):
            await bring._Bring__load_article_translations()


class TestGetUserAccount:
    """Tests for get_user_account method."""

    async def test_get_user_account(self, bring, mocked, monkeypatch):
        """Test for get_user_account."""

        mocked.get(
            f"https://api.getbring.com/rest/v2/bringusers/{UUID}",
            payload=BRING_USER_ACCOUNT_RESPONSE,
            status=200,
        )

        monkeypatch.setattr(bring, "uuid", UUID)
        data = await bring.get_user_account()

        assert data == BRING_USER_ACCOUNT_RESPONSE

    @pytest.mark.parametrize(
        "exception",
        [
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ],
    )
    async def test_request_exception(self, mocked, bring, exception, monkeypatch):
        """Test request exceptions."""

        mocked.get(
            f"https://api.getbring.com/rest/v2/bringusers/{UUID}",
            exception=exception,
        )
        monkeypatch.setattr(bring, "uuid", UUID)

        with pytest.raises(BringRequestException):
            await bring.get_user_account()

    async def test_parse_exception(self, mocked, bring, monkeypatch):
        """Test parse exceptions."""
        mocked.get(
            f"https://api.getbring.com/rest/v2/bringusers/{UUID}",
            status=200,
            body="not json",
            content_type="application/json",
        )
        monkeypatch.setattr(bring, "uuid", UUID)

        with pytest.raises(BringParseException):
            await bring.get_user_account()
