import React, { useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Paper,
  Alert,
  Chip,
  Stack,
  CircularProgress,
  Divider,
  TextField
} from '@mui/material';
import {
  Psychology as PsychologyIcon,
  Search as SearchIcon,
  Analytics as AnalyticsIcon,
  CheckCircle as CheckCircleIcon
} from '@mui/icons-material';
import { CustomColors, FontWeight } from '../../theme';

import QueryGeneration from './QueryGeneration';
import SearchResults from './SearchResults';
import ContentAnalysis from './ContentAnalysis';

const SessionWorkflow = ({ segment, onComplete }) => {
  const [activeStep, setActiveStep] = useState(0);
  const [sessionId, setSessionId] = useState(null);
  const [creatingSession, setCreatingSession] = useState(false);
  const [error, setError] = useState('');
  const [editableFocus, setEditableFocus] = useState(segment.research_focus || '');

  const steps = [
    {
      label: 'Generate Queries',
      description: 'AI generates research queries for your segment',
      icon: <PsychologyIcon />
    },
    {
      label: 'Search Sources',
      description: 'Search selected queries and review sources',
      icon: <SearchIcon />
    },
    {
      label: 'Analyze Content',
      description: 'Generate actionable content themes',
      icon: <AnalyticsIcon />
    }
  ];

  const createSession = async () => {
    setCreatingSession(true);
    setError('');

    try {
      const response = await fetch('https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/intelligence/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          segment_name: segment.name,
          mission: editableFocus
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to create session');
      }

      const result = await response.json();
      
      // Log the response to debug
      console.log('Session created:', result);
      
      // Set session ID from response
      setSessionId(result.session_id);
      
      // Move to first step immediately
      setActiveStep(0);

    } catch (error) {
      console.error('Session creation error:', error);
      setError(error.message);
    } finally {
      setCreatingSession(false);
    }
  };

  const handleQueriesReady = () => {
    setActiveStep(1);
  };

  const handleSearchComplete = () => {
    setActiveStep(2);
  };

  const handleAnalysisComplete = () => {
    if (onComplete) {
      onComplete();
    }
  };

  const renderStepContent = (step) => {
    switch (step) {
      case 0:
        return (
            <QueryGeneration
                sessionId={sessionId}
                segment={segment}
                onQueriesReady={handleQueriesReady}
            />
        );
      case 1:
        return (
            <SearchResults
                sessionId={sessionId}
                onSearchComplete={handleSearchComplete}
            />
        );
      case 2:
        return (
            <ContentAnalysis
                sessionId={sessionId}
                onAnalysisComplete={handleAnalysisComplete}
            />
        );
      default:
        return null;
    }
  };

  const getStepStatus = (stepIndex) => {
    if (stepIndex < activeStep) return 'completed';
    if (stepIndex === activeStep) return 'active';
    return 'pending';
  };

  // Show session creation if no session yet
  if (!sessionId) {
    return (
        <Box>
          <Paper elevation={0} sx={{ p: 3, textAlign: 'left', bgcolor: CustomColors.AliceBlue }}>
            <Box sx={{textAlign: 'center'}}>
              <PsychologyIcon sx={{ fontSize: 48, color: CustomColors.DeepSkyBlue, mb: 2 }} />
              <Typography variant="h6" mb={1}>
                Start Audience Research
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={2}>
                Create a new research session for <strong>{segment.name}</strong>
              </Typography>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" fontWeight={FontWeight.Medium}>Audience:</Typography>
            <Typography variant="body2" color="text.secondary" mb={2}>
              {segment.description}
            </Typography>

            <Typography variant="subtitle2" fontWeight={FontWeight.Medium}>Research Focus:</Typography>
            <TextField
                fullWidth
                multiline
                rows={4}
                variant="outlined"
                value={editableFocus}
                onChange={(e) => setEditableFocus(e.target.value)}
                sx={{ mb: 3, bgcolor: 'white' }}
            />

            <Typography variant="subtitle2" fontWeight={FontWeight.Medium}>Content Goal:</Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              {segment.content_goal}
            </Typography>

            {error && (
                <Alert severity="error" sx={{ mb: 3, textAlign: 'left' }}>
                  {error}
                </Alert>
            )}

            <Button
                variant="contained"
                color="primary"
                onClick={createSession}
                disabled={creatingSession}
                startIcon={creatingSession ? <CircularProgress size={16} /> : <PsychologyIcon />}
                size="large"
            >
              {creatingSession ? 'Creating Session...' : 'Start Research Session'}
            </Button>
          </Paper>
        </Box>
    );
  }

  return (
      <Box>
        {/* Header with Progress */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Box>
            <Typography variant="h5" fontWeight={FontWeight.Bold}>
              Audience Research: {segment.name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Session: {sessionId?.slice(-8)}
            </Typography>
          </Box>

          <Stack direction="row" spacing={1}>
            {steps.map((step, index) => (
                <Chip
                    key={index}
                    icon={step.icon}
                    label={step.label}
                    color={getStepStatus(index) === 'completed' ? 'success' :
                        getStepStatus(index) === 'active' ? 'primary' : 'default'}
                    variant={getStepStatus(index) === 'active' ? 'filled' : 'outlined'}
                    size="small"
                />
            ))}
          </Stack>
        </Box>

        {/* Stepper */}
        <Stepper activeStep={activeStep} orientation="vertical" sx={{ mb: 3 }}>
          {steps.map((step, index) => (
              <Step key={step.label}>
                <StepLabel
                    StepIconComponent={({ active, completed }) => (
                        <Box
                            sx={{
                              width: 32,
                              height: 32,
                              borderRadius: '50%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              backgroundColor: completed ? CustomColors.SecretGarden :
                                  active ? CustomColors.DeepSkyBlue : CustomColors.UIGrey300,
                              color: 'white'
                            }}
                        >
                          {completed ? <CheckCircleIcon sx={{ fontSize: 20 }} /> : step.icon}
                        </Box>
                    )}
                >
                  <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                    {step.label}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {step.description}
                  </Typography>
                </StepLabel>
                <StepContent>
                  <Box mt={2}>
                    {renderStepContent(index)}
                  </Box>
                </StepContent>
              </Step>
          ))}
        </Stepper>
      </Box>
  );
};

export default SessionWorkflow;