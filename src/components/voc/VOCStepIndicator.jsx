import React from 'react';
import {
    Box,
    Chip,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Stack,
    Typography,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import { CustomColors, FontWeight } from '../../theme';

const VOCStepIndicator = ({ steps, currentStep, stepData, canProceedToStep, onStepClick }) => (
    <Box
        sx={{
            width: 280,
            borderRight: `1px solid ${CustomColors.UIGrey300}`,
            bgcolor: CustomColors.UIGrey100,
            p: 3,
        }}
    >
        <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: 0.5, fontSize: 11 }}
        >
            VOC Discovery Pipeline
        </Typography>
        <List sx={{ p: 0 }}>
            {steps.map((step, index) => {
                const stepInfo = stepData[step.id] || {};
                const StepIcon = step.icon;
                const isActive = index === currentStep;
                const isCompleted = stepInfo.status === 'completed';
                const isClickable = canProceedToStep(index);

                return (
                    <React.Fragment key={step.id}>
                        <ListItemButton
                            onClick={() => onStepClick?.(index)}
                            disabled={!isClickable}
                            selected={isActive}
                            sx={{
                                borderRadius: 1,
                                mb: 0.5,
                                '&.Mui-selected': {
                                    bgcolor: CustomColors.DeepSkyBlue + '15',
                                    borderLeft: `3px solid ${CustomColors.DeepSkyBlue}`,
                                },
                            }}
                        >
                            <ListItemIcon sx={{ minWidth: 40 }}>
                                {isCompleted ? (
                                    <CheckCircleIcon color="success" fontSize="small" />
                                ) : (
                                    <RadioButtonUncheckedIcon color={isActive ? 'primary' : 'disabled'} fontSize="small" />
                                )}
                            </ListItemIcon>
                            <ListItemText
                                primary={
                                    <Stack direction="row" spacing={1} alignItems="center">
                                        <StepIcon fontSize="small" />
                                        <Typography fontWeight={FontWeight.Medium}>{step.label}</Typography>
                                    </Stack>
                                }
                                secondary={
                                    <Typography variant="body2" color="text.secondary">
                                        {step.description}
                                    </Typography>
                                }
                            />
                            {stepInfo.duration && (
                                <Chip
                                    label={`${(stepInfo.duration / 1000).toFixed(1)}s`}
                                    size="small"
                                    sx={{ bgcolor: CustomColors.UIGrey200 }}
                                />
                            )}
                        </ListItemButton>
                    </React.Fragment>
                );
            })}
        </List>
    </Box>
);

export default VOCStepIndicator;
