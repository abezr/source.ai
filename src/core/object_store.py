"""
MinIO object storage client module for HBI system.
Provides functionality to upload and manage book files in MinIO.
"""

import os
import uuid
from typing import Optional
import boto3
from botocore.exceptions import ClientError


class ObjectStoreClient:
    """
    MinIO/S3-compatible object storage client.
    """

    def __init__(self):
        """Initialize the MinIO client with environment variables."""
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "books")
        self.client = None

    def _get_client(self):
        """
        Get or create the boto3 client instance.

        Returns:
            boto3.client: S3-compatible client
        """
        if self.client is None:
            self.client = boto3.client(
                's3',
                endpoint_url=f"http{'s' if self.secure else ''}://{self.endpoint}",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name='us-east-1',  # MinIO doesn't use regions, but boto3 requires it
                use_ssl=self.secure
            )
        return self.client

    def ensure_bucket_exists(self) -> None:
        """
        Ensure the books bucket exists, creating it if necessary.

        Raises:
            ClientError: If bucket creation fails
        """
        try:
            client = self._get_client()
            client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # Bucket doesn't exist, create it
                try:
                    client.create_bucket(Bucket=self.bucket_name)
                except ClientError as create_error:
                    raise ClientError(
                        f"Failed to create bucket '{self.bucket_name}': {str(create_error)}"
                    ) from create_error
            else:
                raise ClientError(
                    f"Failed to access bucket '{self.bucket_name}': {str(e)}"
                ) from e

    def upload_file_to_books_bucket(
        self,
        file_object,
        object_name: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file to the books bucket.

        Args:
            file_object: File-like object to upload
            object_name: Name/key for the object in the bucket
            content_type: MIME type of the file (optional)

        Returns:
            str: The object name/key used for storage

        Raises:
            ClientError: If upload fails
        """
        try:
            client = self._get_client()
            self.ensure_bucket_exists()

            # Set default content type if not provided
            if content_type is None:
                if object_name.lower().endswith('.pdf'):
                    content_type = 'application/pdf'
                else:
                    content_type = 'application/octet-stream'

            # Upload the file
            client.upload_fileobj(
                file_object,
                self.bucket_name,
                object_name,
                ExtraArgs={'ContentType': content_type}
            )

            return object_name

        except ClientError as e:
            raise ClientError(f"Failed to upload file '{object_name}': {str(e)}") from e

    def generate_unique_object_name(self, original_filename: str, book_id: int) -> str:
        """
        Generate a unique object name for a book file.

        Args:
            original_filename: Original filename from upload
            book_id: Book ID for uniqueness

        Returns:
            str: Unique object name
        """
        # Extract file extension
        _, ext = os.path.splitext(original_filename)

        # Generate unique identifier
        unique_id = str(uuid.uuid4())[:8]

        # Create object name: books/{book_id}/{unique_id}_{original_name}
        object_name = f"books/{book_id}/{unique_id}_{original_filename}"

        return object_name

    def get_file_url(self, object_name: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for accessing a file.

        Args:
            object_name: Name/key of the object
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            str: Presigned URL
        """
        try:
            client = self._get_client()
            url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            raise ClientError(f"Failed to generate URL for '{object_name}': {str(e)}") from e


# Global client instance
object_store_client = ObjectStoreClient()


def get_object_store_client():
    """
    Dependency injection function for FastAPI endpoints.
    Provides an ObjectStoreClient instance.

    Returns:
        ObjectStoreClient: The object store client instance
    """
    return object_store_client