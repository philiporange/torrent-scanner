"""
Tests for the bencode decoder functionality.
"""

import pytest
from torrent_scanner.bencode import (
    BencodeError,
    bdecode_with_info_span,
    _bdecode_int,
    _bdecode_bytes,
    _bdecode_list,
    _bdecode_dict,
    Decoded
)


class TestBencodeDecoder:
    
    def test_decode_int(self):
        # Positive integer
        result = _bdecode_int(b'i42e', 0)
        assert result.value == 42
        assert result.pos == 4
        
        # Negative integer
        result = _bdecode_int(b'i-123e', 0)
        assert result.value == -123
        assert result.pos == 6
        
        # Zero
        result = _bdecode_int(b'i0e', 0)
        assert result.value == 0
        assert result.pos == 3
    
    def test_decode_int_errors(self):
        # Missing 'e'
        with pytest.raises(BencodeError, match="missing 'e'"):
            _bdecode_int(b'i42', 0)
        
        # Empty integer
        with pytest.raises(BencodeError, match="empty"):
            _bdecode_int(b'ie', 0)
        
        # Invalid -0
        with pytest.raises(BencodeError, match="-0"):
            _bdecode_int(b'i-0e', 0)
        
        # Leading zero
        with pytest.raises(BencodeError, match="leading zero"):
            _bdecode_int(b'i01e', 0)
    
    def test_decode_bytes(self):
        # Simple string
        result = _bdecode_bytes(b'5:hello', 0)
        assert result.value == b'hello'
        assert result.pos == 7
        
        # Empty string
        result = _bdecode_bytes(b'0:', 0)
        assert result.value == b''
        assert result.pos == 2
        
        # Binary data
        result = _bdecode_bytes(b'3:\x00\x01\x02', 0)
        assert result.value == b'\x00\x01\x02'
        assert result.pos == 5
    
    def test_decode_bytes_errors(self):
        # Missing colon
        with pytest.raises(BencodeError, match="missing ':'"):
            _bdecode_bytes(b'5hello', 0)
        
        # Truncated data
        with pytest.raises(BencodeError, match="truncated"):
            _bdecode_bytes(b'5:hell', 0)
    
    def test_decode_list(self):
        # Simple list
        result = _bdecode_list(b'li42e5:helloe', 0)
        assert result.value == [42, b'hello']
        assert result.pos == 13
        
        # Empty list
        result = _bdecode_list(b'le', 0)
        assert result.value == []
        assert result.pos == 2
        
        # Nested list
        result = _bdecode_list(b'lli1ei2eee', 0)
        assert result.value == [[1, 2]]
        assert result.pos == 10
    
    def test_decode_list_errors(self):
        # Unterminated list
        with pytest.raises(BencodeError, match="unterminated"):
            _bdecode_list(b'li42e', 0)
    
    def test_decode_dict(self):
        # Simple dict
        result = _bdecode_dict(b'd3:keyi42ee', 0)
        assert result.value == {b'key': 42}
        assert result.pos == 11
        
        # Empty dict
        result = _bdecode_dict(b'de', 0)
        assert result.value == {}
        assert result.pos == 2
        
        # Multiple keys
        result = _bdecode_dict(b'd1:ai1e1:bi2ee', 0)
        assert result.value == {b'a': 1, b'b': 2}
        assert result.pos == 14
    
    def test_decode_dict_errors(self):
        # Unterminated dict
        with pytest.raises(BencodeError, match="unterminated"):
            _bdecode_dict(b'd3:keyi42e', 0)
    
    def test_bdecode_with_info_span_simple(self):
        # Dict without info key
        data = b'd4:name5:helloe'
        result, info_span = bdecode_with_info_span(data)
        assert result == {b'name': b'hello'}
        assert info_span is None
    
    def test_bdecode_with_info_span_with_info(self):
        # Dict with info key
        data = b'd4:infod4:name5:helloe4:test5:valuee'
        result, info_span = bdecode_with_info_span(data)
        assert result == {b'info': {b'name': b'hello'}, b'test': b'value'}
        assert info_span is not None
        
        # Extract info section and verify it decodes correctly
        info_data = data[info_span[0]:info_span[1]]
        info_dict = _bdecode_dict(info_data, 0)
        assert info_dict.value == {b'name': b'hello'}
    
    def test_bdecode_with_info_span_errors(self):
        # Empty data
        with pytest.raises(BencodeError, match="Empty data"):
            bdecode_with_info_span(b'')
        
        # Not a dict
        with pytest.raises(BencodeError, match="not a dictionary"):
            bdecode_with_info_span(b'i42e')