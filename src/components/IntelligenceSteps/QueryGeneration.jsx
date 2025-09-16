import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Typography,
  Card,
  CardContent,
  Switch,
  FormControlLabel,
  TextField,
  CircularProgress,
  Alert,
  Paper,
  Stack,
  Chip,
  Divider,
  IconButton
} from '@mui/material';
import {
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  Search as SearchIcon,
  Psychology as PsychologyIcon
} from '@mui/icons-material';
import { CustomColors, FontWeight } from '../../../theme';

const QueryGeneration = ({ sessionId, segment, onQueriesReady }) => {
  const [queries, setQueries] = useState([]);
  const [editingQuery, setEditingQuery] = useState(null);
  const [editText, setEditText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sessionData, setSessionData] = useState(null);

  useEffect(() => {
    if (sessionId) {
      loadSession();
    }
  }, [sessionId]);

  const loadSession = async () => {
    try {
      const response = await fetch(`http://localhost:5000/api/intelligence/sessions/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        setSessionData(data);
        setQueries(data.queries || []);
        
        if (data.status === 'queries_ready' && onQueriesReady) {
          onQueriesReady();
        }
      }
    } catch (error) {
      console.error('Failed to load session:', error);
      setError('Failed to load session data');
    }
  };

  const handleQueryToggle = (queryId, selected) => {
    setQueries(prev => prev.map(q => 
      q.id === queryId ? { ...q, selected } : q
    ));
  };

  const handleEditQuery = (query) => {
    setEditingQuery(query.id);
    setEditText(query.text);
  };

  const handleSaveEdit = (queryId) => {
    setQueries(prev => prev.map(q => 
      q.id === queryId ? { ...q, text: editText } : q
    ));
    setEditingQuery(null);
    setEditText('');
  };

  const handleCancelEdit = () => {
    setEditingQuery(null);
    setEditText('');
  };

  const saveQueryChanges = async () => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:5000/api/intelligence/sessions/${sessionId}/queries`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ queries })
      });

      if (!response.ok) {
        throw new Error('Failed to save query changes');
      }

      setError('');
      if (onQueriesReady) {
        onQueriesReady();
      }
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const selectedCount = queries.filter(q => q.selected).length;

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
            Phase 1: Query Generation
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Review and select queries for {segment?.name}
          </Typography>
        </Box>
        <Chip
          icon={<PsychologyIcon />}
          label={`${selectedCount} of ${queries.length} selected`}
          color={selectedCount > 0 ? "primary" : "default"}
          variant="outlined"
        />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Session Info */}
      {sessionData && (
        <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: CustomColors.AliceBlue }}>
          <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
            Research Mission
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {sessionData.mission}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" mt={1}>
            Session: {sessionData.sessionId} • Status: {sessionData.status}
          </Typography>
        </Paper>
      )}

      {/* Queries List */}
      <Stack spacing={2} mb={3}>
        {queries.map((query, index) => (
          <Card 
            key={query.id}
            sx={{
              border: query.selected ? `2px solid ${CustomColors.SecretGarden}` : `1px solid ${CustomColors.UIGrey300}`
            }}
          >
            <CardContent>
              <Box display="flex" alignItems="flex-start" gap={2}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={query.selected}
                      onChange={(e) => handleQueryToggle(query.id, e.target.checked)}
                      color="primary"
                    />
                  }
                  label=""
                  sx={{ margin: 0 }}
                />
                
                <Box flex={1}>
                  <Typography variant="caption" color="text.secondary" mb={1} display="block">
                    Query {index + 1}
                  </Typography>
                  
                  {editingQuery === query.id ? (
                    <Box>
                      <TextField
                        fullWidth
                        multiline
                        rows={2}
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        variant="outlined"
                        size="small"
                        sx={{ mb: 1 }}
                      />
                      <Box display="flex" gap={1}>
                        <IconButton 
                          size="small" 
                          onClick={() => handleSaveEdit(query.id)}
                          color="primary"
                        >
                          <SaveIcon fontSize="small" />
                        </IconButton>
                        <IconButton 
                          size="small" 
                          onClick={handleCancelEdit}
                        >
                          <CancelIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </Box>
                  ) : (
                    <Box>
                      <Typography variant="body2" mb={1}>
                        {query.text}
                      </Typography>
                      <IconButton 
                        size="small" 
                        onClick={() => handleEditQuery(query)}
                        sx={{ opacity: 0.7 }}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  )}
                </Box>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Stack>

      <Divider sx={{ my: 3 }} />

      {/* Action Buttons */}
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography variant="body2" color="text.secondary">
          Select queries to search for relevant content
        </Typography>
        
        <Button
          variant="contained"
          color="primary"
          onClick={saveQueryChanges}
          disabled={loading || selectedCount === 0}
          startIcon={loading ? <CircularProgress size={16} /> : <SearchIcon />}
        >
          {loading ? 'Saving...' : `Proceed with ${selectedCount} Queries`}
        </Button>
      </Box>
    </Box>
  );
};

export default QueryGeneration;