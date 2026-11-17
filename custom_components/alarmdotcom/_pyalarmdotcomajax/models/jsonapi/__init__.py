"""Representations of API objects."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from _pyalarmdotcomajax.models.jsonapi.utils import CamelizerMixin
from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin
from mashumaro.types import Discriminator

if TYPE_CHECKING:
    from _pyalarmdotcomajax.models.jsonapi.jsonapi_types import URI

########################
# JSON:API BASE ENTITY #
########################


@dataclass
class JsonApiBaseElement(CamelizerMixin, DataClassJSONMixin):
    """Base class for JSON:API elements."""

    class Config(BaseConfig):
        """Mashumaro settings for JSON:API elements."""

        serialize_by_alias = True


########################
# JSON:API CORE MODELS #
########################

# fmt: off
# https://www.iana.org/assignments/link-relations/link-relations.xhtml
LinkRelation = Literal["about","acl","alternate","amphtml","appendix","apple-touch-icon","apple-touch-startup-image","archives","author","blocked-by","bookmark","canonical","chapter","cite-as","collection","contents","convertedfrom","copyright","create-form","current","describedby","describes","disclosure","dns-prefetch","duplicate","edit","edit-form","edit-media","enclosure","external","first","glossary","help","hosts","hub","icon","index","intervalafter","intervalbefore","intervalcontains","intervaldisjoint","intervalduring","intervalequals","intervalfinishedby","intervalfinishes","intervalin","intervalmeets","intervalmetby","intervaloverlappedby","intervaloverlaps","intervalstartedby","intervalstarts","item","last","latest-version","license","linkset","lrdd","manifest","mask-icon","me","media-feed","memento","micropub","modulepreload","monitor","monitor-group","next","next-archive","nofollow","noopener","noreferrer","opener","openid2.local_id","openid2.provider","original","p3pv1","payment","pingback","preconnect","predecessor-version","prefetch","preload","prerender","prev","preview","previous","prev-archive","privacy-policy","profile","publication","related","restconf","replies","ruleinput","search","section","self","service","service-desc","service-doc","service-meta","sip-trunking-capability","sponsored","start","status","stylesheet","subsection","successor-version","sunset","tag","terms-of-service","timegate","timemap","type","ugc","up","version-history","via","webmention","working-copy","working-copy-of"]
# https://datatracker.ietf.org/doc/html/rfc8288#section-2.1
LinkLang = Literal["af", "af-ZA", "ar", "ar-AE", "ar-BH", "ar-DZ", "ar-EG", "ar-IQ", "ar-JO", "ar-KW", "ar-LB", "ar-LY", "ar-MA", "ar-OM", "ar-QA", "ar-SA", "ar-SY", "ar-TN", "ar-YE", "az", "az-AZ", "az-Cyrl-AZ", "be", "be-BY", "bg", "bg-BG", "bs-BA", "ca", "ca-ES", "cs", "cs-CZ", "cy", "cy-GB", "da", "da-DK", "de", "de-AT", "de-CH", "de-DE", "de-LI", "de-LU", "dv", "dv-MV", "el", "el-GR", "en", "en-AU", "en-BZ", "en-CA", "en-CB", "en-GB", "en-IE", "en-JM", "en-NZ", "en-PH", "en-TT", "en-US", "en-ZA", "en-ZW", "eo", "es", "es-AR", "es-BO", "es-CL", "es-CO", "es-CR", "es-DO", "es-EC", "es-ES", "es-GT", "es-HN", "es-MX", "es-NI", "es-PA", "es-PE", "es-PR", "es-PY", "es-SV", "es-UY", "es-VE", "et", "et-EE", "eu", "eu-ES", "fa", "fa-IR", "fi", "fi-FI", "fo", "fo-FO", "fr", "fr-BE", "fr-CA", "fr-CH", "fr-FR", "fr-LU", "fr-MC", "gl", "gl-ES", "gu", "gu-IN", "he", "he-IL", "hi", "hi-IN", "hr", "hr-BA", "hr-HR", "hu", "hu-HU", "hy", "hy-AM", "id", "id-ID", "is", "is-IS", "it", "it-CH", "it-IT", "ja", "ja-JP", "ka", "ka-GE", "kk", "kk-KZ", "kn", "kn-IN", "ko", "ko-KR", "kok", "kok-IN", "ky", "ky-KG", "lt", "lt-LT", "lv", "lv-LV", "mi", "mi-NZ", "mk", "mk-MK", "mn", "mn-MN", "mr", "mr-IN", "ms", "ms-BN", "ms-MY", "mt", "mt-MT", "nb", "nb-NO", "nl", "nl-BE", "nl-NL", "nn-NO", "ns", "ns-ZA", "pa", "pa-IN", "pl", "pl-PL", "ps", "ps-AR", "pt", "pt-BR", "pt-PT", "qu", "qu-BO", "qu-EC", "qu-PE", "ro", "ro-RO", "ru", "ru-RU", "sa", "sa-IN", "se", "se-FI", "se-NO", "se-SE", "sk", "sk-SK", "sl", "sl-SI", "sq", "sq-AL", "sr-BA", "sr-Cyrl-BA", "sr-SP", "sr-Cyrl-SP", "sv", "sv-FI", "sv-SE", "sw", "sw-KE", "syr", "syr-SY", "ta", "ta-IN", "te", "te-IN", "th", "th-TH", "tl", "tl-PH", "tn", "tn-ZA", "tr", "tr-TR", "tt", "tt-RU", "ts", "uk", "uk-UA", "ur", "ur-PK", "uz", "uz-UZ", "uz-Cyrl-UZ", "vi", "vi-VN", "xh", "xh-ZA", "zh", "zh-CN", "zh-HK", "zh-MO", "zh-SG", "zh-TW", "zu", "zu-ZA"] # sp
# fmt: on
@dataclass
class Meta(JsonApiBaseElement):
    """
    Represent non-standard meta-information that cannot be represented as an attribute or relationship.

    This meta-information can be used to include any additional information that does not fit within the standard JSON:API specification fields.
    """


@dataclass
class Link(JsonApiBaseElement):
    """
    Define a detailed link object with href and optional meta-information.

    The link object is used to represent hyperlinks. The `href` attribute holds the URL of the link, and `meta` provides additional meta-information about the link.

    This also allows for a string to be used as a link. Strings will be inserted into the href attribute.
    """

    href: URI
    meta: Meta | None = None
    rel: LinkRelation | None = None
    describedby: Link | None = None
    title: str | None = None
    hreflang: LinkLang | None = None


# Link = str | Link

Attributes = dict[str, Any]


@dataclass
class ResourceIdentifier(JsonApiBaseElement):
    """
    Define resource identifier to non-empty members in a relationship object.

    Resource identifier in a compound document allows resources to link in a standard way. Each resource identifier contains `type` and `id` members to identify linked resources uniquely.
    """

    id: str
    type: str
    meta: Meta | None = None


@dataclass
class Jsonapi(JsonApiBaseElement):
    """
    Describe the server's implementation of the JSON:API specification.

    This object includes information about the JSON:API version used by the server and any additional meta-information.
    """

    version: str | None = None
    meta: Meta | None = None


@dataclass
class Source(JsonApiBaseElement):
    """
    Identify the source of a problem in an error response.

    `pointer` is a JSON Pointer to the associated entity in the request document. `parameter` indicates which URI query parameter caused the error.
    """

    pointer: str | None = None
    parameter: str | None = None


@dataclass
class RelatedLinks(JsonApiBaseElement):
    """
    Provide links to related resources.

    Relationships may reference other resource objects and are specified in a resource's links object. This class includes `self` and `related` links to manage the relationships.
    """

    self: Link | None = None
    related: Link | None = None
    describedby: Link | None = None


@dataclass
class PaginatedLinks(RelatedLinks):
    """
    Provide relationship and pagination links for a document.

    Pagination is essential for handling large sets of data. This class includes `first`, `last`, `prev`, and `next` links to navigate through the data pages.
    """

    first: Link | None = None
    last: Link | None = None
    prev: Link | None = None
    next: Link | None = None


# Links = dict[str, Link] | None

ResourceLinkage_HasOne = None | ResourceIdentifier

ResourceLinkage_HasMany = list[ResourceIdentifier]


@dataclass
class Error(JsonApiBaseElement):
    """
    Represent an error that occurred during a request.

    This class captures details about errors in a standardized format, including a unique ID, status code, error code, human-readable title and detail, source of the error, and any additional meta-information.
    """

    id: str | None = field(default=None)
    links: RelatedLinks | None = field(default=None)
    status: str | None = field(default=None)
    code: str | None = field(default=None)
    title: str | None = field(default=None)
    detail: str | None = field(default=None)
    source: Source | None = field(default=None)
    meta: Meta | None = field(default=None)


@dataclass
class Relationship(JsonApiBaseElement):
    """
    Represents a relationship object in a resource.

    Must have at least one of data, links, or meta.
    """

    # TODO: Paginated links can only be present when data is of type ResourceLinkage_HasMany

    data: ResourceLinkage_HasOne | ResourceLinkage_HasMany | None
    links: RelatedLinks | PaginatedLinks | None
    meta: Meta | None

    class Config(BaseConfig):
        """Mashumaro config for Resource."""

        forbidextra_keys = True
        discriminator = Discriminator(include_subtypes=True)

    @property
    def data_list(self) -> list[ResourceIdentifier]:
        """Return data as a list of resource identifiers if applicable."""

        if isinstance(self.data, list):
            return self.data
        if isinstance(self.data, ResourceIdentifier):
            return [self.data]
        return []


@dataclass(kw_only=True)
class DataRelationship(Relationship):
    """Relationship variant with a mandatory data field."""

    data: ResourceLinkage_HasOne | ResourceLinkage_HasMany
    links: RelatedLinks | PaginatedLinks | None = None
    meta: Meta | None = None


@dataclass(kw_only=True)
class MetaRelationship(Relationship):
    """Relationship variant with a mandatory meta field."""

    meta: Meta
    links: RelatedLinks | PaginatedLinks | None = None
    data: ResourceLinkage_HasOne | ResourceLinkage_HasMany | None = None


@dataclass(kw_only=True)
class LinksRelationship(Relationship):
    """Relationship variant with a mandatory links field."""

    links: RelatedLinks | PaginatedLinks
    data: ResourceLinkage_HasOne | ResourceLinkage_HasMany | None = None
    meta: Meta | None = None


Relationships = dict[str, Relationship]


@dataclass(kw_only=True)
class Resource(ResourceIdentifier):
    """
    Represent a single resource object in a JSON:API document.

    Resource objects are key constructs in JSON:API. They include a type, id, optional attributes, relationships, links, and meta-information.
    """

    links: RelatedLinks | None = None
    relationships: Relationships | None = None
    attributes: dict[str, Any]

    # Too annoying to validate types for the entire self.relationships object chain. Instead,
    # we'll just suppress errors and return None/[] if incorrect types are encountered.

    def has_many(self, key: str) -> list[ResourceIdentifier]:
        """Return relationships that are of a specific type or have a specific key."""

        with contextlib.suppress(KeyError, TypeError, AttributeError):
            return [
                linkage
                for linkage in self.relationships[key].data  # type: ignore
                if isinstance(linkage, ResourceIdentifier)
            ]

        return []

    def has_one(self, key: str) -> ResourceIdentifier | None:
        """Return a single resource identifier within a specific relationship key."""

        with contextlib.suppress(KeyError, TypeError, AttributeError):
            if isinstance(resource := self.relationships[key].data, ResourceIdentifier):  # type: ignore
                return resource

        return None

    def all_related_ids(self) -> set[str]:
        """Return resource IDs for all related resources."""

        if not self.relationships:
            return set()

        results = set()
        for value in self.relationships.values():
            if isinstance(value, Relationship):
                if isinstance(value.data, list):
                    results.update([item.id for item in value.data])
                elif isinstance(value.data, ResourceIdentifier):
                    results.add(value.data.id)

        return results

    def all_related_types(self) -> set[str]:
        """Return resource types for all related resources."""

        if not self.relationships:
            return set()

        results = set()
        for relationship in self.relationships.values():
            if str(getattr(relationship.meta, "count", 0)) > "0":
                if isinstance(relationship.data, list):
                    results.update([item.type for item in relationship.data])
                elif isinstance(relationship.data, ResourceIdentifier):
                    results.add(relationship.data.type)

        return results


class Document(JsonApiBaseElement):
    """JSON:API primary response object."""

    class Config(BaseConfig):
        """Mashumaro config for Resource."""

        forbidextra_keys = True
        discriminator = Discriminator(include_subtypes=True)


SuccessDocumentData = (
    Resource | list[Resource] | ResourceIdentifier | list[ResourceIdentifier]
)


@dataclass
class SuccessDocument(Document):
    """
    Represent a successful response in the JSON:API format.

    A successful response includes the primary data (either a single resource or a list of resources), optional included resources, meta-information, links, and JSON:API details.
    """

    # fmt: off
    data: SuccessDocumentData
    included:  list[Resource] | list[ResourceIdentifier] | None = field(default=None)
    meta: Meta | None = field(default=None)
    links: PaginatedLinks | None = field(default=None)
    jsonapi: Jsonapi | None = field(default=None)
    # fmt: on

    def get_included(self, type: str | None) -> list[Resource]:
        """
        Return a list of included resources of a specific type.

        Will return all included resources if no type is specified.
        """

        return [
            resource
            for resource in (self.included or [])
            if (resource.type == type or not type) and isinstance(resource, Resource)
        ]


@dataclass
class FailureDocument(Document):
    """
    Represent a failure response in the JSON:API format.

    A failure response typically contains a list of errors, meta-information, JSON:API object details, and links related to the error or failure.
    """

    errors: list[Error]
    meta: Meta | None = None
    jsonapi: Jsonapi | None = None
    links: PaginatedLinks | None = None

    class Config(BaseConfig):
        """Mashumaro config for Resource."""

        forbidextra_keys = False


@dataclass
class MetaDocument(Document):
    """
    Represent informational data in the JSON:API format.

    This class can be used for responses that primarily convey meta-information and JSON:API details, possibly with additional links.
    """

    meta: Meta
    links: PaginatedLinks | None = None
    jsonapi: Jsonapi | None = None
