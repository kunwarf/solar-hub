"""
Simple file manager for ESP32 web interface.
Allows uploading, listing, and deleting files via web UI.
"""
import os


class FileManager:
    """Manages file operations for web interface."""

    # Files that should not be deleted for safety
    PROTECTED_FILES = ['boot.py', 'webrepl_cfg.py']

    # Maximum upload size (bytes) - adjust based on ESP32 memory
    MAX_UPLOAD_SIZE = 512 * 1024  # 512KB

    @staticmethod
    def list_files(path='/'):
        """
        List all files in the given directory.

        Args:
            path: Directory path (default: root)

        Returns:
            List of dicts with file info: [{name, size, type}, ...]
        """
        files = []
        try:
            for item in os.listdir(path):
                item_path = path + '/' + item if path != '/' else '/' + item
                try:
                    stat = os.stat(item_path)
                    # Check if directory (mode & 0x4000)
                    is_dir = (stat[0] & 0x4000) != 0
                    files.append({
                        'name': item,
                        'path': item_path,
                        'size': stat[6] if not is_dir else 0,
                        'type': 'dir' if is_dir else 'file'
                    })
                except:
                    pass
        except:
            pass

        # Sort: directories first, then files alphabetically
        files.sort(key=lambda x: (0 if x['type'] == 'dir' else 1, x['name']))
        return files

    @staticmethod
    def save_file(filename, content):
        """
        Save content to a file.

        Args:
            filename: File name (e.g., 'main.py')
            content: File content as bytes or string

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure we're writing to root directory
            if '/' in filename or '\\' in filename:
                print("[FileManager] Invalid filename (no paths allowed):", filename)
                return False

            # Check file size
            if len(content) > FileManager.MAX_UPLOAD_SIZE:
                print("[FileManager] File too large:", len(content), "bytes")
                return False

            # Write file
            mode = 'wb' if isinstance(content, bytes) else 'w'
            with open(filename, mode) as f:
                f.write(content)

            print("[FileManager] Saved file:", filename, "({} bytes)".format(len(content)))
            return True

        except Exception as e:
            print("[FileManager] Error saving file:", e)
            return False

    @staticmethod
    def delete_file(filename):
        """
        Delete a file.

        Args:
            filename: File name to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if protected
            if filename in FileManager.PROTECTED_FILES:
                print("[FileManager] Cannot delete protected file:", filename)
                return False

            # Delete file
            os.remove(filename)
            print("[FileManager] Deleted file:", filename)
            return True

        except Exception as e:
            print("[FileManager] Error deleting file:", e)
            return False

    @staticmethod
    def read_file(filename, max_size=100*1024):
        """
        Read file contents.

        Args:
            filename: File to read
            max_size: Maximum bytes to read (default 100KB)

        Returns:
            File content as string, or None if error
        """
        try:
            with open(filename, 'r') as f:
                return f.read(max_size)
        except:
            return None

    @staticmethod
    def format_size(size_bytes):
        """Format size in human-readable format."""
        if size_bytes < 1024:
            return "{} B".format(size_bytes)
        elif size_bytes < 1024 * 1024:
            return "{:.1f} KB".format(size_bytes / 1024)
        else:
            return "{:.1f} MB".format(size_bytes / (1024 * 1024))

    @staticmethod
    def get_disk_usage():
        """
        Get disk usage statistics.

        Returns:
            Dict with total, used, free space in bytes
        """
        try:
            stat = os.statvfs('/')
            total = stat[0] * stat[2]  # block_size * total_blocks
            free = stat[0] * stat[3]   # block_size * free_blocks
            used = total - free

            return {
                'total': total,
                'used': used,
                'free': free,
                'percent': int((used / total) * 100) if total > 0 else 0
            }
        except:
            return None
