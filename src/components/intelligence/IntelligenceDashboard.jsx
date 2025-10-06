import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Divider,
  LinearProgress,
  Alert,
  Paper,
  CircularProgress,
  Breadcrumbs,
  Link
} from '@mui/material';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import PsychologyIcon from '@mui/icons-material/Psychology';
import { CustomColors, FontWeight } from '../../theme';
import SessionWorkflow from '../IntelligenceSteps/SessionWorkflow'; // Ensure this is imported

const IntelligenceDashboard = () => {
  const [config, setConfig] = useState(null);
  const [sessions, setSessions] = useState({});
  const [activeSessions, setActiveSessions] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeSegment, setActiveSegment] = useState(null); // State to manage view

  useEffect(() => {
    // Load config only when the main dashboard is shown
    if (!activeSegment) {
      loadIntelligenceConfig();
    }
  }, [activeSegment]);

  const loadIntelligenceConfig = async () => {
    setLoading(true);
    try {
      const response = await fetch('https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/intelligence/config');
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      } else {
        setError('Failed to load audience research configuration');
      }
    } catch (error) {
      console.error('Failed to load config:', error);
      setError('Failed to connect to audience intelligence API');
    } finally {
      setLoading(false);
    }
  };

  const handleStartOrViewSession = (segment) => {
    setActiveSegment(segment);
  };

  const handleReturnToDashboard = () => {
    setActiveSegment(null);
  };

  // Simplified card for the main dashboard view
  const renderSessionCard = (segment) => {
    const session = sessions[segment.name];
    const status = activeSessions[segment.name];

    return (
        <Card sx={{ height: '100%' }}>
          <CardContent sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
              {segment.name}
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={1} mb={2}>
              {segment.description}
            </Typography>

            <Box sx={{ flexGrow: 1 }} />

            <Divider sx={{ my: 2 }} />

            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Button
                  variant="contained"
                  color="primary"
                  onClick={() => handleStartOrViewSession(segment)}
              >
                {session ? 'View Session' : 'Start Research'}
              </Button>
              {session && (
                  <Chip
                      label={status === 'complete' ? 'Complete' : 'In Progress'}
                      color={status === 'complete' ? 'success' : 'secondary'}
                      size="small"
                      variant="outlined"
                  />
              )}
            </Box>
          </CardContent>
        </Card>
    );
  };


  return (
      <Box>
        {/* Header and Breadcrumbs */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Box>
            <Typography variant="h5" component="h1" fontWeight={FontWeight.Bold}>
              Audience Intelligence
            </Typography>
            <Breadcrumbs separator={<NavigateNextIcon fontSize="small" />} sx={{ mt: 1 }}>
              <Link
                  underline="hover"
                  color={activeSegment ? "primary" : "text.primary"}
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    if(activeSegment) {
                      handleReturnToDashboard();
                    }
                  }}
              >
                Dashboard
              </Link>
              {activeSegment && <Typography color="text.primary">{activeSegment.name}</Typography>}
            </Breadcrumbs>
          </Box>
        </Box>

        {/* Global Loading */}
        {loading && <LinearProgress sx={{ mb: 3 }} />}

        {/* Global Error */}
        {error && (
            <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
              {error}
            </Alert>
        )}

        {/* Conditional Rendering: Show Dashboard or Session Workflow */}
        {activeSegment ? (
            <SessionWorkflow
                key={activeSegment.name}
                segment={activeSegment}
                onComplete={handleReturnToDashboard}
            />
        ) : (
            <Grid container spacing={3}>
              {config?.monthly_run?.segments?.map(renderSessionCard)}
            </Grid>
        )}
      </Box>
  );
};

export default IntelligenceDashboard;